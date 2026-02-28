"""RAG collection management endpoints — full CRUD with RBAC."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.collection import Collection, CollectionPermission, Document
from app.models.user import User
from app.schemas.rag import (
    CollectionCreate,
    CollectionListResponse,
    CollectionPermissionCreate,
    CollectionResponse,
    CollectionUpdate,
)
from app.services.vector_store import vector_store

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────

async def _get_collection_or_404(
    db: AsyncSession,
    collection_id: uuid.UUID,
    user: User,
) -> Collection:
    """Fetch a collection ensuring the user has at least read access."""
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Owner always has access
    if collection.owner_id == user.id:
        return collection

    # Check RBAC permissions
    perm_result = await db.execute(
        select(CollectionPermission).where(
            CollectionPermission.collection_id == collection_id,
            CollectionPermission.role == user.role,
        )
    )
    if perm_result.scalar_one_or_none() is None:
        # Admin override
        if user.role == "admin":
            return collection
        raise HTTPException(status_code=403, detail="Access denied to this collection")

    return collection


async def _require_write_access(
    db: AsyncSession,
    collection: Collection,
    user: User,
) -> None:
    """Raise 403 unless user has write or admin access to the collection."""
    if collection.owner_id == user.id or user.role == "admin":
        return

    result = await db.execute(
        select(CollectionPermission).where(
            CollectionPermission.collection_id == collection.id,
            CollectionPermission.role == user.role,
            CollectionPermission.access_level.in_(["write", "admin"]),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Write access required")


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List collections the current user can access."""
    # Admins see everything; others see owned + permitted
    if user.role == "admin":
        count_stmt = select(func.count()).select_from(Collection)
        items_stmt = select(Collection).order_by(Collection.created_at.desc()).offset(offset).limit(limit)
    else:
        # Collections user owns or has permission for
        permitted_ids_stmt = (
            select(CollectionPermission.collection_id)
            .where(CollectionPermission.role == user.role)
        )
        where_clause = (Collection.owner_id == user.id) | Collection.id.in_(permitted_ids_stmt)
        count_stmt = select(func.count()).select_from(Collection).where(where_clause)
        items_stmt = (
            select(Collection)
            .where(where_clause)
            .order_by(Collection.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(items_stmt)).scalars().all()

    return CollectionListResponse(
        collections=[CollectionResponse.model_validate(c) for c in rows],
        total=total,
    )


@router.post("/collections", response_model=CollectionResponse, status_code=201)
async def create_collection(
    body: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new RAG collection and its Qdrant backing store."""
    collection = Collection(
        name=body.name,
        description=body.description,
        owner_id=user.id,
        classification_level=body.classification_level,
        embedding_model=body.embedding_model,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
    )
    db.add(collection)
    await db.flush()

    # Create the Qdrant collection
    try:
        dim = 768  # nomic-embed-text default
        await vector_store.create_collection(collection.id, vector_size=dim)
    except Exception:
        # Log but don't block — the Qdrant collection can be recreated later
        import logging
        logging.getLogger(__name__).exception("Failed to create Qdrant collection")

    return CollectionResponse.model_validate(collection)


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single collection by ID."""
    collection = await _get_collection_or_404(db, collection_id, user)
    return CollectionResponse.model_validate(collection)


@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: uuid.UUID,
    body: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a collection (owner or write-access required)."""
    collection = await _get_collection_or_404(db, collection_id, user)
    await _require_write_access(db, collection, user)

    update_data = body.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(collection, key, value)

    await db.flush()
    return CollectionResponse.model_validate(collection)


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a collection and its Qdrant backing store (owner or admin required)."""
    collection = await _get_collection_or_404(db, collection_id, user)

    if collection.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the owner or admin can delete a collection")

    # Delete Qdrant collection
    await vector_store.delete_collection(collection_id)

    # Cascade will handle documents, chunks, permissions via FK
    await db.delete(collection)


@router.post("/collections/{collection_id}/permissions", status_code=201)
async def add_permission(
    collection_id: uuid.UUID,
    body: CollectionPermissionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add a role-based permission to a collection (owner or admin only)."""
    collection = await _get_collection_or_404(db, collection_id, user)

    if collection.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the owner or admin can manage permissions")

    perm = CollectionPermission(
        collection_id=collection_id,
        role=body.role,
        access_level=body.access_level,
    )
    db.add(perm)
    return {"message": f"Permission granted: role={body.role}, access={body.access_level}"}

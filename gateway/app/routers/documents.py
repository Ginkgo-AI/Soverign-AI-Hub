"""Document upload endpoint — accepts multipart upload, creates DB record,
queues processing via Redis Streams, returns status."""

import json
import logging
import os
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.collection import Collection, Document
from app.models.user import User
from app.schemas.rag import DocumentListResponse, DocumentResponse, DocumentUploadResponse
from app.services.document_pipeline import SUPPORTED_EXTENSIONS

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = "/tmp/sovereign_ai_uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

REDIS_STREAM = "document_jobs"


# ── Helpers ────────────────────────────────────────────────────────────

def _get_redis() -> aioredis.Redis:
    return aioredis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


async def _ensure_collection_access(
    db: AsyncSession,
    collection_id: uuid.UUID,
    user: User,
) -> Collection:
    """Return collection or raise 404/403."""
    from app.models.collection import CollectionPermission

    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if collection.owner_id == user.id or user.role == "admin":
        return collection

    perm = await db.execute(
        select(CollectionPermission).where(
            CollectionPermission.collection_id == collection_id,
            CollectionPermission.role == user.role,
            CollectionPermission.access_level.in_(["write", "admin"]),
        )
    )
    if perm.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Write access required for this collection")

    return collection


# ── Endpoints ──────────────────────────────────────────────────────────

@router.post(
    "/collections/{collection_id}/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=202,
)
async def upload_document(
    collection_id: uuid.UUID,
    file: UploadFile = File(..., description="File to upload"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a document into a collection.

    The document is saved to disk, a record is created in PostgreSQL,
    and a processing job is queued via Redis Streams. The worker will
    parse, chunk, embed, and store the results.
    """
    # Access check
    collection = await _ensure_collection_access(db, collection_id, user)

    # Validate filename
    filename = file.filename or "unnamed"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Read file with size check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit")

    # Save to disk
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    doc_id = uuid.uuid4()
    temp_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
    with open(temp_path, "wb") as f:
        f.write(content)

    # Create DB record
    document = Document(
        id=doc_id,
        collection_id=collection_id,
        filename=filename,
        file_type=ext.lstrip("."),
        file_size=len(content),
        status="pending",
    )
    db.add(document)
    await db.flush()

    # Queue processing job via Redis Streams
    job_payload = {
        "document_id": str(doc_id),
        "collection_id": str(collection_id),
        "file_path": temp_path,
        "filename": filename,
        "chunk_size": collection.chunk_size,
        "chunk_overlap": collection.chunk_overlap,
        "embedding_model": collection.embedding_model,
    }

    try:
        r = _get_redis()
        await r.xadd(REDIS_STREAM, {"payload": json.dumps(job_payload)})
        await r.aclose()
        logger.info("Queued document processing job: %s", doc_id)
    except Exception:
        logger.exception("Failed to queue processing job for document %s", doc_id)
        # Update status but don't fail the upload — the job can be retried
        document.status = "queue_error"
        await db.flush()

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=filename,
        status=document.status,
        message="Document uploaded and queued for processing",
    )


@router.get(
    "/collections/{collection_id}/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    collection_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List documents in a collection."""
    from app.routers.collections import _get_collection_or_404

    await _get_collection_or_404(db, collection_id, user)

    count_stmt = (
        select(func.count()).select_from(Document).where(Document.collection_id == collection_id)
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    items_stmt = (
        select(Document)
        .where(Document.collection_id == collection_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(items_stmt)).scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in rows],
        total=total,
    )


@router.get(
    "/collections/{collection_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single document by ID."""
    from app.routers.collections import _get_collection_or_404

    await _get_collection_or_404(db, collection_id, user)

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.collection_id == collection_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse.model_validate(doc)


@router.delete("/collections/{collection_id}/documents/{document_id}", status_code=204)
async def delete_document(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a document and its vectors from Qdrant."""
    from app.routers.collections import _get_collection_or_404
    from app.services.vector_store import vector_store

    collection = await _get_collection_or_404(db, collection_id, user)

    # Ownership / write check
    if collection.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the owner or admin can delete documents")

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.collection_id == collection_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove vectors from Qdrant
    try:
        await vector_store.delete_by_document_id(collection_id, str(document_id))
    except Exception:
        logger.exception("Failed to delete vectors for document %s", document_id)

    await db.delete(doc)

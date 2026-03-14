"""Memory system endpoints — CRUD for user memories, knowledge, and summaries."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.memory import ConversationSummary, KnowledgeEntry, UserMemory
from app.schemas.memory import (
    KnowledgeListOut,
    KnowledgeEntryOut,
    MemoryContextOut,
    MemoryListOut,
    SummaryListOut,
    UserMemoryCreate,
    UserMemoryOut,
    UserMemoryUpdate,
)
from app.services.memory_service import get_memory_context

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/memory", response_model=MemoryListOut)
async def list_memories(
    memory_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(UserMemory).where(UserMemory.user_id == user.id)
    if memory_type:
        query = query.where(UserMemory.memory_type == memory_type)
    query = query.order_by(UserMemory.updated_at.desc())

    result = await db.execute(query)
    memories = result.scalars().all()
    return MemoryListOut(
        memories=[UserMemoryOut.model_validate(m) for m in memories],
        total=len(memories),
    )


@router.post("/memory", response_model=UserMemoryOut, status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: UserMemoryCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    memory = UserMemory(
        user_id=user.id,
        memory_type=body.memory_type,
        key=body.key,
        value=body.value,
        confidence=body.confidence,
    )
    db.add(memory)
    await db.flush()
    await db.refresh(memory)
    return UserMemoryOut.model_validate(memory)


@router.put("/memory/{memory_id}", response_model=UserMemoryOut)
async def update_memory(
    memory_id: uuid.UUID,
    body: UserMemoryUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(UserMemory).where(
            and_(UserMemory.id == memory_id, UserMemory.user_id == user.id)
        )
    )
    memory = result.scalar_one_or_none()
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(memory, field, value)
    await db.flush()
    await db.refresh(memory)
    return UserMemoryOut.model_validate(memory)


@router.delete("/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(UserMemory).where(
            and_(UserMemory.id == memory_id, UserMemory.user_id == user.id)
        )
    )
    memory = result.scalar_one_or_none()
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    await db.delete(memory)
    await db.flush()


@router.get("/memory/context", response_model=MemoryContextOut)
async def get_context(
    query: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    ctx = await get_memory_context(db, user.id, query)
    return MemoryContextOut(
        preferences=[UserMemoryOut.model_validate(m) for m in ctx["preferences"]],
        facts=[UserMemoryOut.model_validate(m) for m in ctx["facts"]],
        knowledge=[KnowledgeEntryOut.model_validate(e) for e in ctx["knowledge"]],
        relevant_summaries=[],
        total_memories=ctx["total"],
    )


@router.get("/memory/knowledge", response_model=KnowledgeListOut)
async def list_knowledge(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(KnowledgeEntry)
        .where(
            and_(
                KnowledgeEntry.user_id == user.id,
                KnowledgeEntry.superseded_by == None,  # noqa: E711
            )
        )
        .order_by(KnowledgeEntry.updated_at.desc())
    )
    entries = result.scalars().all()
    return KnowledgeListOut(
        entries=[KnowledgeEntryOut.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.get("/memory/summaries", response_model=SummaryListOut)
async def list_summaries(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(ConversationSummary)
        .where(ConversationSummary.user_id == user.id)
        .order_by(ConversationSummary.updated_at.desc())
        .limit(50)
    )
    summaries = result.scalars().all()
    return SummaryListOut(
        summaries=[],  # Simplified — would need ConversationSummaryOut conversion
        total=len(summaries),
    )


@router.post("/memory/extract")
async def trigger_extraction(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Manually trigger memory extraction for a conversation."""
    from app.services.conversation import get_messages
    from app.services.memory_service import extract_memories

    messages = await get_messages(db, conversation_id)
    api_messages = [{"role": m.role, "content": m.content} for m in messages]

    count = await extract_memories(db, user.id, conversation_id, api_messages)
    return {"extracted": count, "conversation_id": str(conversation_id)}

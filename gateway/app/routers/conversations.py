"""Conversation management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationList,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.services.conversation import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
    update_conversation,
)

router = APIRouter()


@router.get("/conversations", response_model=ConversationList)
async def list_convs(
    search: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = await list_conversations(
        db, user.id, include_archived=include_archived, search=search, limit=limit, offset=offset
    )
    return {"conversations": items, "total": total}


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conv(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = await create_conversation(
        db,
        user_id=user.id,
        title=body.title,
        model_id=body.model_id,
        classification_level=body.classification_level,
        system_prompt=body.system_prompt,
    )
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        model_id=conv.model_id,
        classification_level=conv.classification_level,
        is_archived=conv.is_archived,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=1 if body.system_prompt else 0,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conv(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = await get_conversation(db, conversation_id, user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            tool_call_id=m.tool_call_id,
            token_count=m.token_count,
            created_at=m.created_at,
        )
        for m in sorted(conv.messages, key=lambda m: m.created_at)
    ]

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        model_id=conv.model_id,
        classification_level=conv.classification_level,
        is_archived=conv.is_archived,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(messages),
        messages=messages,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conv(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = await update_conversation(
        db, conversation_id, user.id, **body.model_dump(exclude_none=True)
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conv(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deleted = await delete_conversation(db, conversation_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = await get_conversation(db, conversation_id, user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await get_messages(db, conversation_id)
    return [
        MessageResponse(
            id=m.id, role=m.role, content=m.content, tool_calls=m.tool_calls,
            tool_call_id=m.tool_call_id, token_count=m.token_count, created_at=m.created_at,
        )
        for m in messages
    ]

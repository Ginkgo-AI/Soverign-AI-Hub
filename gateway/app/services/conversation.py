"""Conversation persistence and context window management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, Message


async def create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str = "New Conversation",
    model_id: str = "",
    classification_level: str = "UNCLASSIFIED",
    system_prompt: str | None = None,
) -> Conversation:
    conv = Conversation(
        user_id=user_id,
        title=title,
        model_id=model_id,
        classification_level=classification_level,
    )
    db.add(conv)
    await db.flush()

    if system_prompt:
        msg = Message(
            conversation_id=conv.id,
            role="system",
            content=system_prompt,
        )
        db.add(msg)
        await db.flush()

    return conv


async def list_conversations(
    db: AsyncSession,
    user_id: uuid.UUID,
    include_archived: bool = False,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    query = select(Conversation).where(Conversation.user_id == user_id)

    if not include_archived:
        query = query.where(Conversation.is_archived == False)

    if search:
        query = query.where(Conversation.title.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    conversations = result.scalars().all()

    # Get message counts
    items = []
    for conv in conversations:
        msg_count_q = select(func.count()).where(Message.conversation_id == conv.id)
        msg_count = (await db.execute(msg_count_q)).scalar() or 0
        items.append({
            "id": conv.id,
            "title": conv.title,
            "model_id": conv.model_id,
            "classification_level": conv.classification_level,
            "is_archived": conv.is_archived,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": msg_count,
        })

    return items, total


async def get_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> Conversation | None:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    **updates,
) -> Conversation | None:
    conv = await get_conversation(db, conversation_id, user_id)
    if not conv:
        return None
    for key, value in updates.items():
        if value is not None and hasattr(conv, key):
            setattr(conv, key, value)
    await db.flush()
    return conv


async def delete_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    conv = await get_conversation(db, conversation_id, user_id)
    if not conv:
        return False
    await db.delete(conv)
    await db.flush()
    return True


async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str | None = None,
    tool_calls: dict | list | None = None,
    tool_call_id: str | None = None,
    token_count: int = 0,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        token_count=token_count,
    )
    db.add(msg)

    # Touch conversation updated_at
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        conv.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return msg


async def get_messages(
    db: AsyncSession, conversation_id: uuid.UUID
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())


def build_context_window(
    messages: list[Message],
    max_tokens: int = 8192,
    reserve_for_response: int = 1024,
) -> list[dict]:
    """Build a context window from conversation history that fits within token limits.

    Strategy:
    1. Always keep the system message (first message if role=system)
    2. Always keep the last user message
    3. Fill remaining budget with recent messages, newest first
    4. Rough token estimate: 1 token ≈ 4 chars (conservative)
    """
    if not messages:
        return []

    budget = max_tokens - reserve_for_response
    TOKEN_RATIO = 4  # chars per token estimate

    system_msg = None
    conversation_msgs = []

    for msg in messages:
        entry = {"role": msg.role}
        if msg.content is not None:
            entry["content"] = msg.content
        if msg.tool_calls:
            entry["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id

        if msg.role == "system" and system_msg is None:
            system_msg = entry
        else:
            conversation_msgs.append(entry)

    # Estimate tokens for system message
    used_tokens = 0
    if system_msg:
        used_tokens += len(system_msg.get("content", "")) // TOKEN_RATIO + 10

    # Build from most recent, working backwards
    selected = []
    for msg in reversed(conversation_msgs):
        content = msg.get("content", "") or ""
        msg_tokens = len(content) // TOKEN_RATIO + 10
        if used_tokens + msg_tokens > budget:
            break
        selected.append(msg)
        used_tokens += msg_tokens

    selected.reverse()

    result = []
    if system_msg:
        result.append(system_msg)
    result.extend(selected)

    return result


async def auto_title(
    db: AsyncSession, conversation_id: uuid.UUID, first_user_message: str
) -> None:
    """Generate a title from the first user message (simple truncation for now)."""
    title = first_user_message[:80].strip()
    if len(first_user_message) > 80:
        title += "..."

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv and conv.title == "New Conversation":
        conv.title = title
        await db.flush()

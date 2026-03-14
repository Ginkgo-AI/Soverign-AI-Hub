"""Memory service — extraction, contradiction detection, summarization, context assembly."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import ConversationSummary, KnowledgeEntry, UserMemory
from app.services.llm import llm_backend

logger = logging.getLogger(__name__)

# -- Extraction prompts -------------------------------------------------------

EXTRACT_MEMORIES_PROMPT = """Analyze this conversation and extract structured memories about the user.
Return a JSON object with these arrays:
- "preferences": [{"key": "...", "value": "..."}] — user preferences/settings
- "facts": [{"key": "...", "value": "..."}] — factual info about the user
- "knowledge": [{"subject": "...", "predicate": "...", "object": "..."}] — knowledge triples

Only include items you are confident about. Return empty arrays if nothing to extract.
Return ONLY valid JSON, no markdown or explanation.

Conversation:
{conversation}"""

SUMMARIZE_PROMPT = """Summarize this conversation concisely. Include:
1. Main topics discussed
2. Key decisions or conclusions
3. Any action items

Return a JSON object: {{"summary": "...", "key_topics": ["...", "..."]}}
Return ONLY valid JSON.

Conversation:
{conversation}"""


async def extract_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    messages: list[dict[str, Any]],
) -> int:
    """Extract and persist memories from a conversation. Returns count of new memories."""
    conversation_text = "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}"
        for m in messages
        if m.get("content")
    )

    if len(conversation_text) < 50:
        return 0

    try:
        result = await llm_backend.chat_completion(
            messages=[
                {"role": "system", "content": "You are a memory extraction assistant. Return only valid JSON."},
                {"role": "user", "content": EXTRACT_MEMORIES_PROMPT.format(conversation=conversation_text[:4000])},
            ],
            model="",
            backend="vllm",
            temperature=0.1,
            max_tokens=1024,
            stream=False,
        )

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        data = json.loads(content)
    except Exception:
        logger.exception("Memory extraction failed")
        return 0

    count = 0

    # Persist preferences and facts
    for mem_type in ("preferences", "facts"):
        for item in data.get(mem_type, []):
            key = item.get("key", "").strip()
            value = item.get("value", "").strip()
            if not key or not value:
                continue

            # Check for existing memory with same key
            existing = await db.execute(
                select(UserMemory).where(
                    and_(
                        UserMemory.user_id == user_id,
                        UserMemory.memory_type == mem_type.rstrip("s"),
                        UserMemory.key == key,
                    )
                )
            )
            row = existing.scalar_one_or_none()
            if row:
                row.value = value
                row.source_conversation_id = conversation_id
            else:
                db.add(UserMemory(
                    user_id=user_id,
                    memory_type=mem_type.rstrip("s"),
                    key=key,
                    value=value,
                    source_conversation_id=conversation_id,
                ))
                count += 1

    # Persist knowledge triples
    for triple in data.get("knowledge", []):
        subject = triple.get("subject", "").strip()
        predicate = triple.get("predicate", "").strip()
        obj = triple.get("object", "").strip()
        if not subject or not predicate or not obj:
            continue

        await _detect_and_handle_contradiction(db, user_id, subject, predicate, obj)
        count += 1

    await db.flush()
    logger.info("Extracted %d memories for user %s", count, user_id)
    return count


async def _detect_and_handle_contradiction(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject: str,
    predicate: str,
    new_object: str,
) -> None:
    """Check for contradicting knowledge entries and supersede them."""
    result = await db.execute(
        select(KnowledgeEntry).where(
            and_(
                KnowledgeEntry.user_id == user_id,
                KnowledgeEntry.subject == subject,
                KnowledgeEntry.predicate == predicate,
                KnowledgeEntry.superseded_by == None,  # noqa: E711
            )
        )
    )
    existing = result.scalars().all()

    new_entry = KnowledgeEntry(
        user_id=user_id,
        subject=subject,
        predicate=predicate,
        object_value=new_object,
    )
    db.add(new_entry)
    await db.flush()

    # Mark old entries as superseded
    for old in existing:
        if old.object_value != new_object:
            old.superseded_by = new_entry.id


async def summarize_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    messages: list[dict[str, Any]],
) -> ConversationSummary | None:
    """Generate and persist a conversation summary."""
    conversation_text = "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}"
        for m in messages
        if m.get("content")
    )

    if len(conversation_text) < 100:
        return None

    try:
        result = await llm_backend.chat_completion(
            messages=[
                {"role": "system", "content": "You are a summarization assistant. Return only valid JSON."},
                {"role": "user", "content": SUMMARIZE_PROMPT.format(conversation=conversation_text[:6000])},
            ],
            model="",
            backend="vllm",
            temperature=0.1,
            max_tokens=512,
            stream=False,
        )

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        data = json.loads(content)
    except Exception:
        logger.exception("Conversation summarization failed")
        return None

    # Upsert summary
    existing = await db.execute(
        select(ConversationSummary).where(ConversationSummary.conversation_id == conversation_id)
    )
    summary_row = existing.scalar_one_or_none()

    if summary_row:
        summary_row.summary = data.get("summary", "")
        summary_row.key_topics = data.get("key_topics", [])
        summary_row.message_count = len(messages)
    else:
        summary_row = ConversationSummary(
            conversation_id=conversation_id,
            user_id=user_id,
            summary=data.get("summary", ""),
            key_topics=data.get("key_topics", []),
            message_count=len(messages),
        )
        db.add(summary_row)

    await db.flush()
    return summary_row


async def get_memory_context(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str | None = None,
) -> dict[str, Any]:
    """Assemble relevant memories for prompt injection."""
    # Load all user memories
    mem_result = await db.execute(
        select(UserMemory).where(UserMemory.user_id == user_id).order_by(UserMemory.updated_at.desc()).limit(50)
    )
    memories = mem_result.scalars().all()

    # Load active knowledge entries
    kg_result = await db.execute(
        select(KnowledgeEntry).where(
            and_(
                KnowledgeEntry.user_id == user_id,
                KnowledgeEntry.superseded_by == None,  # noqa: E711
            )
        ).order_by(KnowledgeEntry.updated_at.desc()).limit(30)
    )
    knowledge = kg_result.scalars().all()

    # Load recent summaries
    sum_result = await db.execute(
        select(ConversationSummary)
        .where(ConversationSummary.user_id == user_id)
        .order_by(ConversationSummary.updated_at.desc())
        .limit(5)
    )
    summaries = sum_result.scalars().all()

    return {
        "preferences": [m for m in memories if m.memory_type == "preference"],
        "facts": [m for m in memories if m.memory_type == "fact"],
        "knowledge": knowledge,
        "summaries": summaries,
        "total": len(memories) + len(knowledge),
    }


def inject_memory_into_prompt(
    system_prompt: str,
    memory_context: dict[str, Any],
) -> str:
    """Augment system prompt with relevant memory context."""
    parts = [system_prompt]

    preferences = memory_context.get("preferences", [])
    if preferences:
        pref_lines = [f"- {m.key}: {m.value}" for m in preferences[:10]]
        parts.append(f"\n\n## User Preferences\n" + "\n".join(pref_lines))

    facts = memory_context.get("facts", [])
    if facts:
        fact_lines = [f"- {m.key}: {m.value}" for m in facts[:10]]
        parts.append(f"\n\n## Known Facts About User\n" + "\n".join(fact_lines))

    knowledge = memory_context.get("knowledge", [])
    if knowledge:
        kg_lines = [f"- {e.subject} {e.predicate} {e.object_value}" for e in knowledge[:10]]
        parts.append(f"\n\n## Knowledge\n" + "\n".join(kg_lines))

    summaries = memory_context.get("summaries", [])
    if summaries:
        sum_lines = [f"- {s.summary}" for s in summaries[:3]]
        parts.append(f"\n\n## Recent Conversation Context\n" + "\n".join(sum_lines))

    return "\n".join(parts)

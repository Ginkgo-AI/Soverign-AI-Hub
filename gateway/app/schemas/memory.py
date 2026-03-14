"""Pydantic schemas for the memory system."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserMemoryCreate(BaseModel):
    memory_type: str = Field(..., pattern="^(preference|fact|profile)$")
    key: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class UserMemoryUpdate(BaseModel):
    value: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class UserMemoryOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    memory_type: str
    key: str
    value: str
    confidence: float
    source_conversation_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationSummaryOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    summary: str
    key_topics: list[str]
    message_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeEntryOut(BaseModel):
    id: uuid.UUID
    subject: str
    predicate: str
    object_value: str
    confidence: float
    superseded_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryContextOut(BaseModel):
    """Aggregated memory context for prompt injection."""
    preferences: list[UserMemoryOut] = Field(default_factory=list)
    facts: list[UserMemoryOut] = Field(default_factory=list)
    knowledge: list[KnowledgeEntryOut] = Field(default_factory=list)
    relevant_summaries: list[ConversationSummaryOut] = Field(default_factory=list)
    total_memories: int = 0


class MemoryListOut(BaseModel):
    memories: list[UserMemoryOut]
    total: int


class KnowledgeListOut(BaseModel):
    entries: list[KnowledgeEntryOut]
    total: int


class SummaryListOut(BaseModel):
    summaries: list[ConversationSummaryOut]
    total: int

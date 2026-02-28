"""Pydantic schemas for Edge Device management — Phase 8."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Edge Device CRUD
# ---------------------------------------------------------------------------


class EdgeDeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    agent_id: str | None = None  # Auto-generated if not supplied
    classification_level: str = "UNCLASSIFIED"
    metadata: dict | None = None


class EdgeDeviceOut(BaseModel):
    id: uuid.UUID
    name: str
    agent_id: str
    status: str
    last_seen: datetime | None = None
    sync_state: dict | None = None
    config_version: str
    classification_level: str
    metadata: dict | None = Field(None, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class EdgeDeviceRegisterOut(EdgeDeviceOut):
    """Returned only at registration — includes the plaintext API key."""

    api_key: str


class EdgeDeviceListOut(BaseModel):
    devices: list[EdgeDeviceOut]
    total: int


class EdgeDeviceUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    classification_level: str | None = None
    config_version: str | None = None
    metadata: dict | None = None


# ---------------------------------------------------------------------------
# Sync payloads
# ---------------------------------------------------------------------------


class SyncConversationMessage(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


class SyncConversation(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class SyncConversationPayload(BaseModel):
    agent_id: str
    conversation: SyncConversation
    messages: list[SyncConversationMessage]


class SyncKnowledgeChunk(BaseModel):
    id: str
    collection_id: str
    content: str
    metadata: str = "{}"
    created_at: str


class SyncKnowledgePayload(BaseModel):
    chunks: list[SyncKnowledgeChunk]


class SyncResponse(BaseModel):
    status: str = "ok"
    items_received: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# Sync / status helpers
# ---------------------------------------------------------------------------


class EdgeStatusOut(BaseModel):
    device_id: uuid.UUID
    name: str
    agent_id: str
    status: str
    last_seen: datetime | None
    sync_state: dict | None
    config_version: str
    classification_level: str


class EdgeConfigPush(BaseModel):
    config_version: str
    classification_level: str | None = None
    allowed_models: list[str] | None = None
    policy: dict | None = None


class EdgeModelInfo(BaseModel):
    name: str
    filename: str
    size_bytes: int
    quantization: str | None = None
    description: str = ""

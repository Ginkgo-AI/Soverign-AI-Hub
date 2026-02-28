import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    role: str
    content: str | None = None
    tool_calls: dict | list | None = None
    tool_call_id: str | None = None


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str | None
    tool_calls: dict | list | None = None
    tool_call_id: str | None = None
    token_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    model_id: str = ""
    classification_level: str = "UNCLASSIFIED"
    system_prompt: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = None
    model_id: str | None = None
    classification_level: str | None = None
    is_archived: bool | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    model_id: str
    classification_level: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationResponse):
    messages: list[MessageResponse] = []


class ConversationList(BaseModel):
    conversations: list[ConversationResponse]
    total: int


class SystemPromptCreate(BaseModel):
    name: str
    content: str
    description: str = ""


class SystemPromptResponse(BaseModel):
    id: uuid.UUID
    name: str
    content: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}

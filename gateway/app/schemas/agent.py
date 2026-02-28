"""Pydantic schemas for Agent CRUD, execution, and tool-calling operations."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

class ToolDefinition(BaseModel):
    """OpenAI function-calling tool definition."""

    type: str = "function"
    function: dict[str, Any] = Field(
        ...,
        description="OpenAI function schema with name, description, parameters",
    )


class ToolResult(BaseModel):
    """Structured result returned by every tool execution."""

    success: bool
    output: Any | None = None
    error: str | None = None
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Agent definition CRUD
# ---------------------------------------------------------------------------

class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    system_prompt: str = Field(..., min_length=1)
    model_id: str = ""
    tools: list[str] = Field(
        default_factory=list,
        description="List of tool names this agent may use",
    )
    permissions: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_id: str | None = None
    tools: list[str] | None = None
    permissions: dict[str, Any] | None = None


class AgentOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    system_prompt: str
    model_id: str
    tools: list[str]
    permissions: dict[str, Any]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListOut(BaseModel):
    agents: list[AgentOut]
    total: int


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

class ExecuteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=32_000)
    conversation_history: list[dict[str, Any]] | None = None
    max_iterations: int = Field(default=20, ge=1, le=100)
    timeout_seconds: float = Field(default=300.0, ge=10, le=3600)


class StepOut(BaseModel):
    id: uuid.UUID
    step_number: int
    action: str
    tool_name: str | None = None
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    duration_ms: int = 0
    requires_approval: bool = False
    approved_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    input_prompt: str
    final_output: str | None = None
    total_steps: int = 0
    total_tokens: int = 0
    created_at: datetime
    updated_at: datetime
    steps: list[StepOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ExecutionStartOut(BaseModel):
    """Returned immediately when an execution is kicked off."""

    execution_id: uuid.UUID
    status: str
    message: str = "Execution started"


class ExecutionResultOut(BaseModel):
    """Full result returned when the agent loop finishes."""

    execution_id: uuid.UUID
    status: str
    final_output: str | None = None
    total_steps: int = 0
    total_tokens: int = 0
    steps: list[StepOut] = Field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Approval / cancellation
# ---------------------------------------------------------------------------

class ApproveRequest(BaseModel):
    step_id: uuid.UUID


class ApproveOut(BaseModel):
    execution_id: uuid.UUID
    step_id: uuid.UUID
    status: str
    message: str


class CancelOut(BaseModel):
    execution_id: uuid.UUID
    status: str
    message: str


# ---------------------------------------------------------------------------
# Tool listing
# ---------------------------------------------------------------------------

class ToolInfo(BaseModel):
    name: str
    description: str
    category: str
    parameters_schema: dict[str, Any]
    requires_approval: bool


class ToolListOut(BaseModel):
    tools: list[ToolInfo]
    total: int

"""Pydantic schemas for work mode (multi-step task execution)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkObjectiveRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=32_000)
    max_tasks: int = Field(default=10, ge=1, le=50)
    max_iterations_per_task: int = Field(default=10, ge=1, le=50)
    timeout_seconds: float = Field(default=600.0, ge=30, le=7200)


class WorkTaskOut(BaseModel):
    id: uuid.UUID
    execution_id: uuid.UUID
    parent_task_id: uuid.UUID | None = None
    title: str
    description: str
    status: str
    depends_on: list[str]
    task_order: int
    output: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkProgressOut(BaseModel):
    execution_id: uuid.UUID
    objective: str
    status: str
    tasks: list[WorkTaskOut]
    completed_count: int
    total_count: int
    current_task: str | None = None

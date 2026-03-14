"""Pydantic schemas for automation (schedules, watchers, logs)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# -- Schedules ---------------------------------------------------------------

class ScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    cron_expression: str = Field(..., min_length=1, max_length=100)
    agent_id: uuid.UUID
    prompt: str = Field(..., min_length=1)
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    agent_id: uuid.UUID | None = None
    prompt: str | None = None
    enabled: bool | None = None


class ScheduleOut(BaseModel):
    id: uuid.UUID
    name: str
    cron_expression: str
    agent_id: uuid.UUID
    prompt: str
    enabled: bool
    last_run_at: datetime | None = None
    last_status: str | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleListOut(BaseModel):
    schedules: list[ScheduleOut]
    total: int


# -- Watchers ----------------------------------------------------------------

class WatcherCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    watch_path: str = Field(..., min_length=1)
    file_pattern: str = "*"
    action_type: str = Field(..., pattern="^(ingest|agent)$")
    collection_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    prompt_template: str | None = None
    enabled: bool = True


class WatcherUpdate(BaseModel):
    name: str | None = None
    watch_path: str | None = None
    file_pattern: str | None = None
    action_type: str | None = None
    collection_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    prompt_template: str | None = None
    enabled: bool | None = None


class WatcherOut(BaseModel):
    id: uuid.UUID
    name: str
    watch_path: str
    file_pattern: str
    action_type: str
    collection_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    prompt_template: str | None = None
    enabled: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WatcherListOut(BaseModel):
    watchers: list[WatcherOut]
    total: int


# -- Automation logs ---------------------------------------------------------

class AutomationLogOut(BaseModel):
    id: uuid.UUID
    trigger_type: str
    trigger_id: uuid.UUID
    status: str
    execution_id: uuid.UUID | None = None
    details: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AutomationLogListOut(BaseModel):
    logs: list[AutomationLogOut]
    total: int

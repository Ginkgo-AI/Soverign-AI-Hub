"""Pydantic schemas for tool plugins."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    name: str
    description: str = ""
    version: str = "0.1.0"
    author: str = ""
    category: str = "plugin"
    requires_approval: bool = True
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class PluginCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    version: str = "0.1.0"
    category: str = "plugin"
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    handler_module: str = Field(..., min_length=1, description="Python source code for the handler")
    requires_approval: bool = True
    manifest: dict[str, Any] | None = None


class PluginUpdate(BaseModel):
    description: str | None = None
    version: str | None = None
    category: str | None = None
    parameters_schema: dict[str, Any] | None = None
    handler_module: str | None = None
    requires_approval: bool | None = None
    manifest: dict[str, Any] | None = None


class PluginOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    version: str
    category: str
    parameters_schema: dict[str, Any]
    requires_approval: bool
    enabled: bool
    source: str
    manifest: dict[str, Any] | None = None
    installed_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PluginListOut(BaseModel):
    plugins: list[PluginOut]
    total: int

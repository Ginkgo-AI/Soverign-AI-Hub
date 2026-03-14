"""Pydantic schemas for skills/capability registry."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SkillCatalogOut(BaseModel):
    """Lightweight catalog view for browsing."""
    id: uuid.UUID
    name: str
    description: str
    category: str
    catalog_summary: str
    icon: str
    version: str
    enabled: bool

    model_config = {"from_attributes": True}


class SkillFullOut(BaseModel):
    """Complete skill definition loaded on demand."""
    id: uuid.UUID
    name: str
    description: str
    version: str
    category: str
    catalog_summary: str
    icon: str
    system_prompt: str
    tool_configuration: list[str]
    example_prompts: list[str]
    parameters: dict[str, Any]
    source_type: str
    enabled: bool
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    version: str = "1.0.0"
    category: str = Field(..., min_length=1)
    catalog_summary: str = ""
    icon: str = "sparkles"
    system_prompt: str = Field(..., min_length=1)
    tool_configuration: list[str] = Field(default_factory=list)
    example_prompts: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    category: str | None = None
    catalog_summary: str | None = None
    icon: str | None = None
    system_prompt: str | None = None
    tool_configuration: list[str] | None = None
    example_prompts: list[str] | None = None
    parameters: dict[str, Any] | None = None
    enabled: bool | None = None


class SkillCatalogListOut(BaseModel):
    skills: list[SkillCatalogOut]
    total: int

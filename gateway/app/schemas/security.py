"""Security, audit, RBAC, and compliance schemas for Phase 6."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
class ClassificationLevel(str, Enum):
    UNCLASSIFIED = "UNCLASSIFIED"
    CUI = "CUI"
    FOUO = "FOUO"
    SECRET = "SECRET"
    TOP_SECRET = "TOP_SECRET"


CLASSIFICATION_HIERARCHY: dict[ClassificationLevel, int] = {
    ClassificationLevel.UNCLASSIFIED: 0,
    ClassificationLevel.CUI: 1,
    ClassificationLevel.FOUO: 2,
    ClassificationLevel.SECRET: 3,
    ClassificationLevel.TOP_SECRET: 4,
}


CLASSIFICATION_BANNERS: dict[ClassificationLevel, dict[str, str]] = {
    ClassificationLevel.UNCLASSIFIED: {
        "color": "#4ade80",
        "bg": "#166534",
        "label": "UNCLASSIFIED",
        "warning": "",
    },
    ClassificationLevel.CUI: {
        "color": "#60a5fa",
        "bg": "#1e3a5f",
        "label": "CUI - CONTROLLED UNCLASSIFIED INFORMATION",
        "warning": "Handle in accordance with CUI policy.",
    },
    ClassificationLevel.FOUO: {
        "color": "#fb923c",
        "bg": "#7c2d12",
        "label": "FOR OFFICIAL USE ONLY",
        "warning": "Not for public release. Distribution limited.",
    },
    ClassificationLevel.SECRET: {
        "color": "#f87171",
        "bg": "#7f1d1d",
        "label": "SECRET",
        "warning": "Unauthorized disclosure could cause serious damage to national security.",
    },
    ClassificationLevel.TOP_SECRET: {
        "color": "#fbbf24",
        "bg": "#78350f",
        "label": "TOP SECRET",
        "warning": "Unauthorized disclosure could cause exceptionally grave damage to national security.",
    },
}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AuditLogEntry(BaseModel):
    id: int
    timestamp: datetime
    user_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    request_summary: str | None = None
    response_summary: str | None = None
    model_id: str | None = None
    token_count: int = 0
    ip_address: str | None = None
    classification_level: str = "UNCLASSIFIED"
    metadata_: dict[str, Any] | None = Field(None, alias="metadata")

    model_config = {"from_attributes": True, "populate_by_name": True}


class AuditLogQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)
    user_id: uuid.UUID | None = None
    action: str | None = None
    resource_type: str | None = None
    classification_level: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None


class AuditLogExport(BaseModel):
    format: str = Field("json", pattern="^(json|csv|syslog)$")
    date_from: datetime | None = None
    date_to: datetime | None = None


class AuditStats(BaseModel):
    total_events: int
    events_today: int
    events_this_week: int
    top_actions: list[dict[str, Any]]
    top_users: list[dict[str, Any]]
    events_by_day: list[dict[str, Any]]
    events_by_classification: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------
class RolePermission(BaseModel):
    role: str
    permissions: dict[str, list[str]]


class UserRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(admin|manager|analyst|viewer)$")


class UserActiveUpdate(BaseModel):
    is_active: bool


# ---------------------------------------------------------------------------
# Security configuration
# ---------------------------------------------------------------------------
class SecurityConfig(BaseModel):
    airgap_mode: bool
    classification_levels: list[str]
    session_timeout_minutes: int
    max_concurrent_sessions: int
    encryption_enabled: bool
    audit_retention_days: int
    siem_endpoint: str
    keycloak_enabled: bool


class SecurityConfigUpdate(BaseModel):
    airgap_mode: bool | None = None
    session_timeout_minutes: int | None = None
    max_concurrent_sessions: int | None = None
    audit_retention_days: int | None = None
    siem_endpoint: str | None = None


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------
class ComplianceControl(BaseModel):
    control_id: str
    control_name: str
    control_family: str
    status: str = Field(..., pattern="^(implemented|partial|planned|not_applicable)$")
    evidence: str
    notes: str


class ComplianceReport(BaseModel):
    generated_at: datetime
    framework: str = "NIST 800-53"
    overall_score: float
    total_controls: int
    implemented: int
    partial: int
    planned: int
    controls: list[ComplianceControl]

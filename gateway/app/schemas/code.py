"""Pydantic schemas for Code Assistant endpoints -- Phase 5."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Workspace schemas
# ---------------------------------------------------------------------------

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    path: str
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    file_tree: "list[FileTreeNode] | None" = None

    model_config = {"from_attributes": True}


class WorkspaceListOut(BaseModel):
    workspaces: list[WorkspaceOut]
    total: int


# ---------------------------------------------------------------------------
# File tree schemas
# ---------------------------------------------------------------------------

class FileTreeNode(BaseModel):
    name: str
    path: str  # relative path within workspace
    is_dir: bool = False
    size: int = 0
    language: str | None = None
    line_count: int | None = None
    children: "list[FileTreeNode] | None" = None


class FileContent(BaseModel):
    path: str
    content: str
    language: str | None = None
    size: int = 0
    line_count: int = 0


class FileWriteRequest(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Code execution schemas
# ---------------------------------------------------------------------------

class ExecuteRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = Field(default="python", pattern=r"^(python|javascript|bash|sql)$")
    session_id: uuid.UUID | None = None
    timeout: int = Field(default=30, ge=1, le=300)


class ExecuteResponse(BaseModel):
    execution_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    stdout: str = ""
    stderr: str = ""
    return_value: str | None = None
    exit_code: int = 0
    execution_time_ms: float = 0.0
    language: str = "python"


# ---------------------------------------------------------------------------
# Code analysis schemas
# ---------------------------------------------------------------------------

class AnalysisIssue(BaseModel):
    line: int | None = None
    column: int | None = None
    severity: str = "warning"  # info, warning, error
    message: str = ""
    rule: str | None = None


class AnalyzeRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = "python"
    analysis_type: str = Field(
        default="full",
        description="Type of analysis: full, security, bugs, style",
    )


class AnalyzeResponse(BaseModel):
    issues: list[AnalysisIssue] = Field(default_factory=list)
    summary: str = ""
    issue_count: int = 0
    language: str = "python"


# ---------------------------------------------------------------------------
# Code generation / explanation / review schemas
# ---------------------------------------------------------------------------

class CodeGenRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=16000)
    language: str = "python"
    context: str | None = None


class CodeGenResponse(BaseModel):
    code: str = ""
    explanation: str = ""
    language: str = "python"


class ExplainRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = "python"
    detail_level: str = Field(
        default="normal",
        description="Level of detail: brief, normal, detailed",
    )


class ExplainResponse(BaseModel):
    explanation: str = ""
    language: str = "python"


class ReviewRequest(BaseModel):
    code: str | None = None
    diff: str | None = None
    language: str = "python"
    focus: str = Field(
        default="general",
        description="Review focus: general, security, performance, bugs",
    )


class ReviewFinding(BaseModel):
    line: int | None = None
    severity: str = "info"  # info, warning, error, critical
    category: str = ""
    message: str = ""
    suggestion: str | None = None


class ReviewResponse(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: str = ""
    overall_quality: str = "acceptable"  # poor, acceptable, good, excellent


# ---------------------------------------------------------------------------
# Git schemas
# ---------------------------------------------------------------------------

class GitDiffSummaryRequest(BaseModel):
    diff: str = Field(..., min_length=1)


class GitDiffSummary(BaseModel):
    summary: str = ""
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    file_summaries: list[dict[str, str]] = Field(default_factory=list)


class CommitMessageRequest(BaseModel):
    diff: str = Field(..., min_length=1)
    style: str = Field(
        default="conventional",
        description="Commit message style: conventional, descriptive, brief",
    )


class CommitMessageResponse(BaseModel):
    message: str = ""
    subject: str = ""
    body: str = ""


# Resolve forward references
WorkspaceOut.model_rebuild()
FileTreeNode.model_rebuild()

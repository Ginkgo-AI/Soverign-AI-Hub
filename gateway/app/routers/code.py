"""
Code Assistant router -- Phase 5.

Provides endpoints for workspace management, code execution, analysis,
LLM-powered code generation/review, and git operations.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.code import CodeExecution, CodeSession, CodeWorkspace
from app.schemas.code import (
    AnalyzeRequest,
    AnalyzeResponse,
    CodeGenRequest,
    CodeGenResponse,
    CommitMessageRequest,
    CommitMessageResponse,
    ExecuteRequest,
    ExecuteResponse,
    ExplainRequest,
    ExplainResponse,
    FileContent,
    FileWriteRequest,
    GitDiffSummary,
    GitDiffSummaryRequest,
    ReviewRequest,
    ReviewResponse,
    ReviewFinding,
    WorkspaceCreate,
    WorkspaceListOut,
    WorkspaceOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------

@router.post("/code/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a new code workspace."""
    from app.services.code_workspace import create_workspace_dir

    ws_id = uuid.uuid4()
    ws_path = create_workspace_dir(user.id, ws_id)

    workspace = CodeWorkspace(
        id=ws_id,
        name=body.name,
        description=body.description,
        user_id=user.id,
        path=str(ws_path),
    )
    db.add(workspace)
    await db.flush()
    await db.refresh(workspace)

    return WorkspaceOut.model_validate(workspace)


@router.get("/code/workspaces", response_model=WorkspaceListOut)
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all workspaces for the current user."""
    result = await db.execute(
        select(CodeWorkspace)
        .where(CodeWorkspace.user_id == user.id)
        .order_by(CodeWorkspace.created_at.desc())
    )
    workspaces = result.scalars().all()
    return WorkspaceListOut(
        workspaces=[WorkspaceOut.model_validate(ws) for ws in workspaces],
        total=len(workspaces),
    )


@router.get("/code/workspaces/{ws_id}", response_model=WorkspaceOut)
async def get_workspace(
    ws_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get workspace details including file tree."""
    from app.services.code_workspace import build_file_tree

    result = await db.execute(
        select(CodeWorkspace).where(
            CodeWorkspace.id == ws_id,
            CodeWorkspace.user_id == user.id,
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws_path = Path(workspace.path)
    file_tree = build_file_tree(ws_path) if ws_path.exists() else []

    out = WorkspaceOut.model_validate(workspace)
    out.file_tree = file_tree
    return out


@router.delete("/code/workspaces/{ws_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    ws_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete a workspace and all its files."""
    from app.services.code_workspace import delete_workspace_dir

    result = await db.execute(
        select(CodeWorkspace).where(
            CodeWorkspace.id == ws_id,
            CodeWorkspace.user_id == user.id,
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    delete_workspace_dir(workspace.path)
    await db.delete(workspace)
    await db.flush()


@router.post("/code/workspaces/{ws_id}/upload")
async def upload_to_workspace(
    ws_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Upload a zip/tar archive and extract into the workspace."""
    from app.services.code_workspace import extract_upload

    result = await db.execute(
        select(CodeWorkspace).where(
            CodeWorkspace.id == ws_id,
            CodeWorkspace.user_id == user.id,
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(status_code=400, detail="File too large (max 100MB)")

    try:
        count = extract_upload(Path(workspace.path), content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"message": f"Extracted {count} files", "files_extracted": count}


# ---------------------------------------------------------------------------
# File operations within workspace
# ---------------------------------------------------------------------------

@router.get("/code/workspaces/{ws_id}/files/{path:path}", response_model=FileContent)
async def read_workspace_file(
    ws_id: uuid.UUID,
    path: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Read a file from a workspace."""
    from app.services.code_workspace import read_file

    workspace = await _get_workspace(ws_id, user.id, db)
    try:
        return read_file(Path(workspace.path), path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.put("/code/workspaces/{ws_id}/files/{path:path}", response_model=FileContent)
async def write_workspace_file(
    ws_id: uuid.UUID,
    path: str,
    body: FileWriteRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Write or update a file in a workspace."""
    from app.services.code_workspace import write_file

    workspace = await _get_workspace(ws_id, user.id, db)
    try:
        return write_file(Path(workspace.path), path, body.content)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete("/code/workspaces/{ws_id}/files/{path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_file(
    ws_id: uuid.UUID,
    path: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete a file or directory from a workspace."""
    from app.services.code_workspace import delete_file

    workspace = await _get_workspace(ws_id, user.id, db)
    try:
        delete_file(Path(workspace.path), path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Not found: {path}")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


# ---------------------------------------------------------------------------
# Code execution
# ---------------------------------------------------------------------------

@router.post("/code/execute", response_model=ExecuteResponse)
async def execute_code_endpoint(
    body: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Execute code in a sandboxed environment."""
    from app.services.code_sandbox import execute_code, get_or_create_session

    session = get_or_create_session(body.session_id, body.language)

    result = await execute_code(
        code=body.code,
        language=body.language,
        session_id=session.id,
        timeout=body.timeout,
    )

    # Persist execution record
    db_session = None
    if body.session_id:
        db_result = await db.execute(
            select(CodeSession).where(CodeSession.id == body.session_id)
        )
        db_session = db_result.scalar_one_or_none()

    if db_session is None:
        db_session = CodeSession(
            id=session.id,
            user_id=user.id,
            language=body.language,
        )
        db.add(db_session)
        await db.flush()

    execution = CodeExecution(
        session_id=db_session.id,
        code=body.code,
        language=body.language,
        stdout=result["stdout"],
        stderr=result["stderr"],
        return_value=result.get("return_value"),
        execution_time_ms=int(result.get("execution_time_ms", 0)),
        exit_code=result.get("exit_code", 0),
    )
    db.add(execution)
    await db.flush()
    await db.refresh(execution)

    return ExecuteResponse(
        execution_id=execution.id,
        session_id=db_session.id,
        stdout=result["stdout"],
        stderr=result["stderr"],
        return_value=result.get("return_value"),
        exit_code=result.get("exit_code", 0),
        execution_time_ms=result.get("execution_time_ms", 0),
        language=body.language,
    )


# ---------------------------------------------------------------------------
# Code analysis
# ---------------------------------------------------------------------------

@router.post("/code/analyze", response_model=AnalyzeResponse)
async def analyze_code_endpoint(
    body: AnalyzeRequest,
    user=Depends(get_current_user),
):
    """Perform static analysis on code."""
    from app.services.code_analysis import analyze_code

    return analyze_code(
        code=body.code,
        language=body.language,
        analysis_type=body.analysis_type,
    )


@router.post("/code/explain", response_model=ExplainResponse)
async def explain_code_endpoint(
    body: ExplainRequest,
    user=Depends(get_current_user),
):
    """Explain code using the LLM."""
    from app.services.code_analysis import explain_code_with_llm

    explanation = await explain_code_with_llm(
        code=body.code,
        language=body.language,
        detail_level=body.detail_level,
    )
    return ExplainResponse(explanation=explanation, language=body.language)


@router.post("/code/generate", response_model=CodeGenResponse)
async def generate_code_endpoint(
    body: CodeGenRequest,
    user=Depends(get_current_user),
):
    """Generate code from a natural language description."""
    from app.services.code_analysis import generate_code_with_llm

    result = await generate_code_with_llm(
        prompt=body.prompt,
        language=body.language,
        context=body.context,
    )
    return CodeGenResponse(
        code=result["code"],
        explanation=result["explanation"],
        language=body.language,
    )


@router.post("/code/review", response_model=ReviewResponse)
async def review_code_endpoint(
    body: ReviewRequest,
    user=Depends(get_current_user),
):
    """Review code or diff for bugs, security issues, etc."""
    from app.services.code_analysis import review_code_with_llm

    if not body.code and not body.diff:
        raise HTTPException(status_code=400, detail="Either code or diff is required")

    review_text = await review_code_with_llm(
        code=body.code,
        diff=body.diff,
        language=body.language,
        focus=body.focus,
    )

    return ReviewResponse(
        findings=[
            ReviewFinding(
                severity="info",
                category="review",
                message=review_text,
            )
        ],
        summary=review_text[:500],
        overall_quality="acceptable",
    )


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------

@router.post("/code/git/diff-summary", response_model=GitDiffSummary)
async def diff_summary_endpoint(
    body: GitDiffSummaryRequest,
    user=Depends(get_current_user),
):
    """Summarize a git diff using LLM."""
    from app.services.code_analysis import summarize_diff

    result = await summarize_diff(body.diff)
    return GitDiffSummary(**result)


@router.post("/code/git/commit-message", response_model=CommitMessageResponse)
async def commit_message_endpoint(
    body: CommitMessageRequest,
    user=Depends(get_current_user),
):
    """Generate a commit message from a diff."""
    from app.services.code_analysis import generate_commit_message

    result = await generate_commit_message(body.diff, body.style)
    return CommitMessageResponse(**result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_workspace(
    ws_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> CodeWorkspace:
    """Fetch workspace or raise 404."""
    result = await db.execute(
        select(CodeWorkspace).where(
            CodeWorkspace.id == ws_id,
            CodeWorkspace.user_id == user_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

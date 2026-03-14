"""
Agent management and execution endpoints -- Phase 3 Agentic Runtime.

Provides full CRUD for agent definitions plus execution lifecycle:
  - start / status / approve / cancel

Adapted from Metis_2/backend/api/agentic.py for the Sovereign AI Hub.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.agent import AgentDefinition, AgentExecution, AgentStep
from app.schemas.agent import (
    AgentCreate,
    AgentListOut,
    AgentOut,
    AgentUpdate,
    ApproveOut,
    ApproveRequest,
    CancelOut,
    ExecuteRequest,
    ExecutionOut,
    ExecutionResultOut,
    ExecutionStartOut,
    StepOut,
    ToolInfo,
    ToolListOut,
)
from app.services.tool_registry import tool_registry

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_to_out(agent: AgentDefinition) -> AgentOut:
    return AgentOut.model_validate(agent)


# ---------------------------------------------------------------------------
# Default / seed agent definitions
# ---------------------------------------------------------------------------

_DEFAULT_AGENTS: list[dict[str, Any]] = [
    {
        "name": "General Assistant",
        "description": "A general-purpose assistant that can search, calculate, and help with various tasks.",
        "system_prompt": (
            "You are a helpful general-purpose AI assistant running inside a sovereign, "
            "air-gapped environment. Use the tools provided to answer questions accurately. "
            "Always prefer using tools over answering from memory."
        ),
        "model_id": "",
        "tools": ["rag_search", "calculator", "http_request"],
        "permissions": {"roles": ["analyst", "admin"]},
    },
    {
        "name": "Data Analyst",
        "description": "Analyses data using SQL queries, calculations, and Python code.",
        "system_prompt": (
            "You are a data analyst assistant. Use SQL queries to explore the database, "
            "Python for calculations and transformations, and the calculator for quick math. "
            "Present findings clearly with numbers and summaries."
        ),
        "model_id": "",
        "tools": ["sql_query", "python_exec", "calculator", "rag_search"],
        "permissions": {"roles": ["analyst", "admin"]},
    },
    {
        "name": "Researcher",
        "description": "Searches documents and synthesises research summaries.",
        "system_prompt": (
            "You are a research assistant. Search the document collections to find "
            "relevant information, then synthesise clear summaries. Cite the sources "
            "you used. If you cannot find information, say so honestly."
        ),
        "model_id": "",
        "tools": ["rag_search", "file_read", "calculator"],
        "permissions": {"roles": ["analyst", "admin"]},
    },
    {
        "name": "Code Assistant",
        "description": "Writes, executes, and debugs code in Python and Bash.",
        "system_prompt": (
            "You are a coding assistant. Write clean, well-documented code. "
            "You can execute Python and Bash to test solutions. Read and write "
            "files in the workspace as needed. Always explain what your code does."
        ),
        "model_id": "",
        "tools": ["python_exec", "bash_exec", "file_read", "file_write", "calculator"],
        "permissions": {"roles": ["admin"]},
    },
]


async def seed_default_agents(db: AsyncSession, created_by: uuid.UUID) -> None:
    """Insert default agent definitions if the table is empty."""
    count_result = await db.execute(select(func.count(AgentDefinition.id)))
    if count_result.scalar_one() > 0:
        return

    for defn in _DEFAULT_AGENTS:
        agent = AgentDefinition(
            name=defn["name"],
            description=defn["description"],
            system_prompt=defn["system_prompt"],
            model_id=defn["model_id"],
            tools=defn["tools"],
            permissions=defn["permissions"],
            created_by=created_by,
        )
        db.add(agent)
    await db.flush()
    logger.info("Seeded %d default agent definitions", len(_DEFAULT_AGENTS))


# =========================================================================
# CRUD endpoints
# =========================================================================

@router.get("/agents", response_model=AgentListOut)
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all agent definitions."""
    result = await db.execute(
        select(AgentDefinition).order_by(AgentDefinition.created_at)
    )
    agents = result.scalars().all()
    return AgentListOut(
        agents=[_agent_to_out(a) for a in agents],
        total=len(agents),
    )


@router.post("/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a new agent definition."""
    agent = AgentDefinition(
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        model_id=body.model_id,
        tools=body.tools,
        permissions=body.permissions,
        created_by=user.id,
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return _agent_to_out(agent)


@router.get("/agents/tools", response_model=ToolListOut)
async def list_tools(user=Depends(get_current_user)):
    """List all registered tools."""
    specs = tool_registry.list_tools()
    return ToolListOut(
        tools=[
            ToolInfo(
                name=s.name,
                description=s.description,
                category=s.category,
                parameters_schema=s.parameters_schema,
                requires_approval=s.requires_approval,
            )
            for s in specs
        ],
        total=len(specs),
    )


@router.get("/agents/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get an agent definition by ID."""
    result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_out(agent)


@router.put("/agents/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Update an agent definition."""
    result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)
    await db.flush()
    await db.refresh(agent)
    return _agent_to_out(agent)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete an agent definition."""
    result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.flush()


# =========================================================================
# Execution endpoints
# =========================================================================

@router.post(
    "/agents/{agent_id}/execute",
    response_model=ExecutionResultOut,
    status_code=status.HTTP_200_OK,
)
async def execute_agent(
    agent_id: uuid.UUID,
    body: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Start an agent execution.

    Runs the full agentic tool-calling loop synchronously and returns the
    result.  For very long tasks the client should use a generous timeout.
    """
    # Fetch agent
    result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Create execution row
    execution = AgentExecution(
        agent_id=agent.id,
        user_id=user.id,
        status="running",
        input_prompt=body.prompt,
    )
    db.add(execution)
    await db.flush()

    # Import here to avoid circular imports
    from app.services.agent_executor import run_agent

    agent_result = await run_agent(
        agent=agent,
        execution=execution,
        prompt=body.prompt,
        db=db,
        conversation_history=body.conversation_history,
        max_iterations=body.max_iterations,
        timeout_seconds=body.timeout_seconds,
    )

    # Load steps for response
    steps_result = await db.execute(
        select(AgentStep)
        .where(AgentStep.execution_id == execution.id)
        .order_by(AgentStep.step_number)
    )
    steps = steps_result.scalars().all()

    return ExecutionResultOut(
        execution_id=execution.id,
        status=agent_result.status,
        final_output=agent_result.final_output,
        total_steps=len(steps),
        total_tokens=agent_result.total_tokens,
        steps=[StepOut.model_validate(s) for s in steps],
        error=agent_result.error,
    )


@router.get("/agents/executions/{exec_id}", response_model=ExecutionOut)
async def get_execution(
    exec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get execution status and steps."""
    result = await db.execute(
        select(AgentExecution).where(AgentExecution.id == exec_id)
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Load steps
    steps_result = await db.execute(
        select(AgentStep)
        .where(AgentStep.execution_id == exec_id)
        .order_by(AgentStep.step_number)
    )
    steps = steps_result.scalars().all()

    return ExecutionOut(
        id=execution.id,
        agent_id=execution.agent_id,
        user_id=execution.user_id,
        status=execution.status,
        input_prompt=execution.input_prompt,
        final_output=execution.final_output,
        total_steps=execution.total_steps,
        total_tokens=execution.total_tokens,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
        steps=[StepOut.model_validate(s) for s in steps],
    )


@router.post("/agents/executions/{exec_id}/approve", response_model=ApproveOut)
async def approve_step(
    exec_id: uuid.UUID,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Approve a paused tool-call step and resume execution.
    """
    # Validate execution exists and is paused
    exec_result = await db.execute(
        select(AgentExecution).where(AgentExecution.id == exec_id)
    )
    execution = exec_result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    if execution.status != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Execution is not paused (status={execution.status})",
        )

    # Validate step exists and requires approval
    step_result = await db.execute(
        select(AgentStep).where(
            AgentStep.id == body.step_id,
            AgentStep.execution_id == exec_id,
        )
    )
    step = step_result.scalar_one_or_none()
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    if not step.requires_approval:
        raise HTTPException(status_code=400, detail="Step does not require approval")

    # Mark approved
    step.approved_by = user.id
    step.requires_approval = False
    await db.flush()

    # Resume execution
    from app.services.agent_executor import resume_after_approval

    agent_result = await resume_after_approval(
        execution=execution,
        approved_step=step,
        db=db,
    )

    return ApproveOut(
        execution_id=exec_id,
        step_id=body.step_id,
        status=agent_result.status,
        message=f"Step approved and execution resumed. Final status: {agent_result.status}",
    )


# =========================================================================
# Cryptographic identity endpoints (Phase E)
# =========================================================================

@router.post("/agents/{agent_id}/identity")
async def assign_agent_identity(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Generate and assign a cryptographic identity to an agent."""
    from app.services.agent_identity import assign_identity
    try:
        result = await assign_identity(db, agent_id)
        return {"agent_id": str(agent_id), **result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/agents/{agent_id}/actions")
async def list_agent_actions(
    agent_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List signed actions for an agent."""
    from app.models.agent_identity import AgentAction
    result = await db.execute(
        select(AgentAction)
        .where(AgentAction.agent_id == agent_id)
        .order_by(AgentAction.created_at.desc())
        .limit(limit)
    )
    actions = result.scalars().all()
    return {
        "actions": [
            {
                "id": str(a.id),
                "action_type": a.action_type,
                "action_hash": a.action_hash,
                "signature": a.signature[:20] + "...",
                "payload_summary": a.payload_summary,
                "created_at": a.created_at.isoformat(),
            }
            for a in actions
        ],
        "total": len(actions),
    }


@router.post("/agents/{agent_id}/verify")
async def verify_agent_action(
    agent_id: uuid.UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Verify a signed action."""
    action_id = body.get("action_id")
    if not action_id:
        raise HTTPException(status_code=400, detail="action_id required")

    from app.models.agent_identity import AgentAction
    from app.services.agent_identity import verify_action
    import json

    # Load the action
    action_result = await db.execute(
        select(AgentAction).where(AgentAction.id == uuid.UUID(action_id))
    )
    action = action_result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    # Load the agent's public key
    agent_result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None or not agent.public_key:
        raise HTTPException(status_code=400, detail="Agent has no cryptographic identity")

    # Verify
    payload = json.loads(action.payload_summary) if action.payload_summary else {}
    verified = verify_action(agent.public_key, payload, action.signature)

    return {"action_id": action_id, "verified": verified}


@router.post("/agents/executions/{exec_id}/cancel", response_model=CancelOut)
async def cancel_execution(
    exec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Cancel a running or paused execution."""
    result = await db.execute(
        select(AgentExecution).where(AgentExecution.id == exec_id)
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel execution with status={execution.status}",
        )

    execution.status = "cancelled"
    await db.flush()

    return CancelOut(
        execution_id=exec_id,
        status="cancelled",
        message="Execution cancelled successfully",
    )

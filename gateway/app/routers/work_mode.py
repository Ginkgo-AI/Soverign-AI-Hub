"""Work mode endpoints — multi-step task execution."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.agent import AgentDefinition, AgentExecution
from app.models.work_task import WorkTask
from app.schemas.work_mode import WorkObjectiveRequest, WorkProgressOut, WorkTaskOut
from app.services.work_mode import decompose_objective, execute_work_plan, get_work_progress

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/agents/{agent_id}/work")
async def start_work_mode(
    agent_id: uuid.UUID,
    body: WorkObjectiveRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Load agent
    result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Create execution
    execution = AgentExecution(
        agent_id=agent.id,
        user_id=user.id,
        status="running",
        input_prompt=body.objective,
        objective=body.objective,
        work_mode=True,
    )
    db.add(execution)
    await db.flush()

    # Decompose objective into tasks
    tasks = await decompose_objective(db, execution, body.objective, body.max_tasks)

    # Execute the work plan
    final_status = await execute_work_plan(
        agent=agent,
        execution=execution,
        tasks=tasks,
        db=db,
        max_iterations_per_task=body.max_iterations_per_task,
        timeout_seconds=body.timeout_seconds,
    )

    execution.status = final_status
    await db.flush()

    progress = await get_work_progress(db, execution.id)

    return WorkProgressOut(
        execution_id=execution.id,
        objective=body.objective,
        status=final_status,
        tasks=[WorkTaskOut.model_validate(t) for t in progress["tasks"]],
        completed_count=progress["completed_count"],
        total_count=progress["total_count"],
        current_task=progress["current_task"],
    )


@router.get("/agents/work/{execution_id}", response_model=WorkProgressOut)
async def get_work_status(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(AgentExecution).where(AgentExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    progress = await get_work_progress(db, execution_id)

    return WorkProgressOut(
        execution_id=execution_id,
        objective=execution.objective or execution.input_prompt,
        status=execution.status,
        tasks=[WorkTaskOut.model_validate(t) for t in progress["tasks"]],
        completed_count=progress["completed_count"],
        total_count=progress["total_count"],
        current_task=progress["current_task"],
    )

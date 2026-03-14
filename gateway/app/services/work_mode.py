"""Work mode service — objective decomposition and multi-step task execution."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentDefinition, AgentExecution
from app.models.work_task import WorkTask
from app.services.agent_executor import run_agent
from app.services.llm import llm_backend

logger = logging.getLogger(__name__)

DECOMPOSE_PROMPT = """Decompose this objective into a sequence of concrete subtasks.
Each task should be independently executable by an AI agent with tool access.

Return a JSON array of tasks, each with:
- "title": short task title
- "description": detailed instructions for the agent
- "depends_on": array of task indices (0-based) this task depends on

Order tasks so dependencies come first. Maximum {max_tasks} tasks.
Return ONLY valid JSON array.

Objective: {objective}"""


async def decompose_objective(
    db: AsyncSession,
    execution: AgentExecution,
    objective: str,
    max_tasks: int = 10,
) -> list[WorkTask]:
    """Use LLM to break objective into WorkTask rows with dependency graph."""
    try:
        result = await llm_backend.chat_completion(
            messages=[
                {"role": "system", "content": "You decompose complex objectives into subtasks. Return only valid JSON."},
                {"role": "user", "content": DECOMPOSE_PROMPT.format(objective=objective, max_tasks=max_tasks)},
            ],
            model="",
            backend="vllm",
            temperature=0.2,
            max_tokens=2048,
            stream=False,
        )
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        tasks_data = json.loads(content)
    except Exception:
        logger.exception("Objective decomposition failed")
        # Fallback: single task
        tasks_data = [{"title": "Execute objective", "description": objective, "depends_on": []}]

    if not isinstance(tasks_data, list):
        tasks_data = [{"title": "Execute objective", "description": objective, "depends_on": []}]

    # Create WorkTask rows
    tasks: list[WorkTask] = []
    task_id_map: dict[int, uuid.UUID] = {}

    for idx, td in enumerate(tasks_data[:max_tasks]):
        task = WorkTask(
            execution_id=execution.id,
            title=td.get("title", f"Task {idx + 1}"),
            description=td.get("description", ""),
            status="pending",
            depends_on=[],  # Will resolve after all IDs assigned
            task_order=idx,
        )
        db.add(task)
        await db.flush()
        task_id_map[idx] = task.id
        tasks.append(task)

    # Resolve dependency references (index -> UUID)
    for idx, td in enumerate(tasks_data[:max_tasks]):
        dep_indices = td.get("depends_on", [])
        dep_ids = [str(task_id_map[d]) for d in dep_indices if d in task_id_map and d != idx]
        tasks[idx].depends_on = dep_ids

    await db.flush()
    logger.info("Decomposed objective into %d tasks for execution %s", len(tasks), execution.id)
    return tasks


def _topological_sort(tasks: list[WorkTask]) -> list[WorkTask]:
    """Sort tasks respecting dependency order."""
    id_to_task = {str(t.id): t for t in tasks}
    visited: set[str] = set()
    result: list[WorkTask] = []

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        visited.add(task_id)
        task = id_to_task.get(task_id)
        if task is None:
            return
        for dep_id in task.depends_on:
            visit(dep_id)
        result.append(task)

    for t in tasks:
        visit(str(t.id))

    return result


async def execute_work_plan(
    *,
    agent: AgentDefinition,
    execution: AgentExecution,
    tasks: list[WorkTask],
    db: AsyncSession,
    max_iterations_per_task: int = 10,
    timeout_seconds: float = 600.0,
) -> str:
    """Execute tasks in dependency order. Returns final status."""
    sorted_tasks = _topological_sort(tasks)
    start_time = time.time()
    completed_outputs: dict[str, str] = {}

    for task in sorted_tasks:
        # Check timeout
        if time.time() - start_time > timeout_seconds:
            task.status = "skipped"
            task.error = "Work plan timeout exceeded"
            continue

        # Check dependencies are met
        unmet = [d for d in task.depends_on if d not in completed_outputs]
        if unmet:
            # Check if any dependency failed
            failed_deps = [d for d in task.depends_on
                          if any(t.status == "failed" and str(t.id) == d for t in sorted_tasks)]
            if failed_deps:
                task.status = "skipped"
                task.error = "Dependency failed"
                continue

        task.status = "running"
        await db.flush()

        # Build prompt with context from completed tasks
        context_parts = []
        for dep_id in task.depends_on:
            if dep_id in completed_outputs:
                dep_task = next((t for t in sorted_tasks if str(t.id) == dep_id), None)
                if dep_task:
                    context_parts.append(f"[Result of '{dep_task.title}']: {completed_outputs[dep_id][:1000]}")

        task_prompt = task.description
        if context_parts:
            task_prompt = "Context from previous tasks:\n" + "\n".join(context_parts) + "\n\nCurrent task: " + task_prompt

        # Create a sub-execution for this task
        sub_execution = AgentExecution(
            agent_id=agent.id,
            user_id=execution.user_id,
            status="running",
            input_prompt=task_prompt,
        )
        db.add(sub_execution)
        await db.flush()

        try:
            agent_result = await run_agent(
                agent=agent,
                execution=sub_execution,
                prompt=task_prompt,
                db=db,
                max_iterations=max_iterations_per_task,
                timeout_seconds=min(120.0, timeout_seconds - (time.time() - start_time)),
            )

            if agent_result.status == "completed":
                task.status = "completed"
                task.output = agent_result.final_output
                completed_outputs[str(task.id)] = agent_result.final_output or ""
            else:
                task.status = "failed"
                task.error = agent_result.error or "Task execution failed"
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            logger.exception("Work task '%s' failed", task.title)

        await db.flush()

    # Determine overall status
    statuses = [t.status for t in sorted_tasks]
    if all(s == "completed" for s in statuses):
        return "completed"
    elif any(s == "completed" for s in statuses):
        return "partial"
    else:
        return "failed"


async def get_work_progress(
    db: AsyncSession,
    execution_id: uuid.UUID,
) -> dict[str, Any]:
    """Get current progress of a work plan."""
    result = await db.execute(
        select(WorkTask)
        .where(WorkTask.execution_id == execution_id)
        .order_by(WorkTask.task_order)
    )
    tasks = result.scalars().all()

    completed = sum(1 for t in tasks if t.status == "completed")
    current = next((t for t in tasks if t.status == "running"), None)

    return {
        "tasks": tasks,
        "completed_count": completed,
        "total_count": len(tasks),
        "current_task": current.title if current else None,
    }

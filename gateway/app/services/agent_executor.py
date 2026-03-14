"""
Agent Executor -- the core agentic tool-calling loop.

Adapted from Metis_2/backend/services/agentic_executor.py for the
Sovereign AI Hub.

Flow:
  1. Build message list (system prompt + conversation history + user prompt)
  2. Send to LLM with tool definitions
  3. If LLM returns tool_calls -> execute each tool
  4. Append tool results -> send back to LLM
  5. Repeat until LLM returns plain text or guards trigger
  6. Persist every step into ``agent_steps`` table

Guards:
  - max_iterations (default 20)
  - timeout (default 300 s)
  - human-in-the-loop: pause if tool requires_approval
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentDefinition, AgentExecution, AgentStep
from app.services.llm import llm_backend
from app.services.tool_executor import execute_tool
from app.services.tool_registry import tool_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class AgentResult:
    """Value object returned by ``run_agent``."""

    __slots__ = (
        "execution_id",
        "status",
        "final_output",
        "steps",
        "total_tokens",
        "error",
    )

    def __init__(
        self,
        execution_id: uuid.UUID,
        status: str = "completed",
        final_output: str | None = None,
        steps: list[dict[str, Any]] | None = None,
        total_tokens: int = 0,
        error: str | None = None,
    ):
        self.execution_id = execution_id
        self.status = status
        self.final_output = final_output
        self.steps = steps or []
        self.total_tokens = total_tokens
        self.error = error


# ---------------------------------------------------------------------------
# Core loop
# ---------------------------------------------------------------------------

async def run_agent(
    *,
    agent: AgentDefinition,
    execution: AgentExecution,
    prompt: str,
    db: AsyncSession,
    conversation_history: list[dict[str, Any]] | None = None,
    max_iterations: int = 20,
    timeout_seconds: float = 300.0,
) -> AgentResult:
    """
    Execute the agentic tool-calling loop.

    Parameters
    ----------
    agent : AgentDefinition
        The agent definition containing system_prompt, model_id, tools list.
    execution : AgentExecution
        A freshly-created row in ``agent_executions`` (status=running).
    prompt : str
        The user's natural-language request.
    db : AsyncSession
        Active database session for persisting steps.
    conversation_history : list | None
        Optional prior messages.
    max_iterations : int
        Safety guard -- max tool-calling loops.
    timeout_seconds : float
        Safety guard -- wall-clock timeout for the entire execution.

    Returns
    -------
    AgentResult
    """
    start_time = time.time()
    step_number = 0
    total_tokens = 0
    steps_log: list[dict[str, Any]] = []

    # -- Build message list -------------------------------------------------
    messages: list[dict[str, Any]] = []
    if agent.system_prompt:
        messages.append({"role": "system", "content": agent.system_prompt})
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": prompt})

    # -- Resolve tool definitions -------------------------------------------
    agent_tool_names: list[str] = agent.tools or []
    openai_tools = tool_registry.get_openai_tools(
        agent_tool_names if agent_tool_names else None
    )

    logger.info(
        "Agent loop started: execution=%s agent=%s tools=%d max_iter=%d",
        execution.id,
        agent.name,
        len(openai_tools),
        max_iterations,
    )

    # -- Main loop ----------------------------------------------------------
    for iteration in range(max_iterations):
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger.warning("Agent execution timed out after %.1fs", elapsed)
            await _finish_execution(
                db, execution, "failed", None, step_number, total_tokens
            )
            return AgentResult(
                execution_id=execution.id,
                status="failed",
                error=f"Execution timed out after {timeout_seconds}s",
                steps=steps_log,
                total_tokens=total_tokens,
            )

        # --- call LLM -----------------------------------------------------
        step_number += 1
        llm_start = time.time()

        try:
            result = await llm_backend.chat_completion(
                messages=messages,
                model=agent.model_id or "",
                backend="vllm",
                temperature=0.3,
                max_tokens=4096,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto" if openai_tools else None,
            )
        except Exception as exc:
            logger.error("LLM call failed: %s", exc, exc_info=True)
            await _persist_step(
                db, execution.id, step_number, "think", None,
                {"messages_count": len(messages)},
                {"error": str(exc)},
                int((time.time() - llm_start) * 1000),
            )
            await _finish_execution(
                db, execution, "failed", None, step_number, total_tokens
            )
            return AgentResult(
                execution_id=execution.id,
                status="failed",
                error=str(exc),
                steps=steps_log,
                total_tokens=total_tokens,
            )

        llm_duration_ms = int((time.time() - llm_start) * 1000)

        # Extract usage
        usage = result.get("usage", {})
        total_tokens += usage.get("total_tokens", 0)

        # Extract the assistant message
        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "")
        content = message.get("content")
        tool_calls = message.get("tool_calls")

        # Persist the "think" step (LLM response)
        think_step = await _persist_step(
            db, execution.id, step_number, "think", None,
            {"messages_count": len(messages), "iteration": iteration + 1},
            {"content": content, "tool_calls_count": len(tool_calls) if tool_calls else 0,
             "finish_reason": finish_reason},
            llm_duration_ms,
        )
        steps_log.append({
            "step": step_number,
            "action": "think",
            "duration_ms": llm_duration_ms,
        })

        # --- No tool calls -> final response -------------------------------
        if not tool_calls:
            final_text = content or ""
            logger.info(
                "Agent loop done: execution=%s iterations=%d steps=%d tokens=%d",
                execution.id,
                iteration + 1,
                step_number,
                total_tokens,
            )
            await _finish_execution(
                db, execution, "completed", final_text, step_number, total_tokens
            )
            return AgentResult(
                execution_id=execution.id,
                status="completed",
                final_output=final_text,
                steps=steps_log,
                total_tokens=total_tokens,
            )

        # --- Process tool calls --------------------------------------------
        # Add assistant message with tool_calls to conversation
        messages.append(message)

        for tc in tool_calls:
            tc_id = tc.get("id", str(uuid.uuid4()))
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            try:
                arguments = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}

            # Check if tool requires approval
            registered = tool_registry.get(tool_name)
            needs_approval = registered.spec.requires_approval if registered else False

            step_number += 1

            if needs_approval:
                # Persist a paused step and halt execution
                paused_step = await _persist_step(
                    db, execution.id, step_number, "tool_call", tool_name,
                    arguments, None, 0,
                    requires_approval=True,
                )
                steps_log.append({
                    "step": step_number,
                    "action": "tool_call",
                    "tool_name": tool_name,
                    "requires_approval": True,
                })

                await _finish_execution(
                    db, execution, "paused", None, step_number, total_tokens
                )
                return AgentResult(
                    execution_id=execution.id,
                    status="paused",
                    final_output=None,
                    steps=steps_log,
                    total_tokens=total_tokens,
                )

            # Execute tool
            tool_start = time.time()
            tool_result = await execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                user_id=str(execution.user_id),
            )
            tool_duration = int((time.time() - tool_start) * 1000)

            # Persist tool_call step
            await _persist_step(
                db, execution.id, step_number, "tool_call", tool_name,
                arguments, tool_result, tool_duration,
            )
            steps_log.append({
                "step": step_number,
                "action": "tool_call",
                "tool_name": tool_name,
                "success": tool_result.get("success", False),
                "duration_ms": tool_duration,
            })

            # Persist tool_result step
            step_number += 1
            await _persist_step(
                db, execution.id, step_number, "tool_result", tool_name,
                {"tool_call_id": tc_id},
                tool_result, 0,
            )

            # Sign tool action if agent has identity
            try:
                from app.services.agent_identity import record_signed_action
                await record_signed_action(
                    db, agent.id, execution.id, "tool_call",
                    {"tool_name": tool_name, "arguments": arguments},
                )
            except Exception:
                pass  # Identity signing is optional

            # Append tool result message for LLM
            result_content = json.dumps(tool_result)
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result_content,
            })

        # Continue loop -- LLM will process tool results

    # -- Max iterations exhausted -------------------------------------------
    logger.warning("Max iterations reached: execution=%s", execution.id)
    await _finish_execution(
        db, execution, "failed", None, step_number, total_tokens
    )
    return AgentResult(
        execution_id=execution.id,
        status="failed",
        error=f"Max iterations ({max_iterations}) reached",
        steps=steps_log,
        total_tokens=total_tokens,
    )


# ---------------------------------------------------------------------------
# Resume after approval
# ---------------------------------------------------------------------------

async def resume_after_approval(
    *,
    execution: AgentExecution,
    approved_step: AgentStep,
    db: AsyncSession,
    max_iterations: int = 20,
    timeout_seconds: float = 300.0,
) -> AgentResult:
    """
    Resume a paused execution after a tool step has been approved.

    Executes the approved tool, then continues the normal agent loop.
    """
    # Load the agent definition
    agent_result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.id == execution.agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        return AgentResult(
            execution_id=execution.id,
            status="failed",
            error="Agent definition not found",
        )

    # Execute the previously-paused tool
    tool_name = approved_step.tool_name or ""
    arguments = approved_step.input_data or {}

    tool_start = time.time()
    tool_result = await execute_tool(
        tool_name=tool_name,
        arguments=arguments,
        user_id=str(execution.user_id),
    )
    tool_duration = int((time.time() - tool_start) * 1000)

    # Update the step with the result
    approved_step.output_data = tool_result
    approved_step.duration_ms = tool_duration
    await db.flush()

    # Rebuild messages from all steps
    messages = await _rebuild_messages(agent, execution, db)

    # Append the tool result to messages
    messages.append({
        "role": "tool",
        "tool_call_id": str(approved_step.id),
        "content": json.dumps(tool_result),
    })

    # Mark execution as running again
    execution.status = "running"
    await db.flush()

    # Continue the loop using the standard run_agent function's inner logic
    # For simplicity, we re-call run_agent with the rebuilt history
    # but we need to continue from where we left off
    openai_tools = tool_registry.get_openai_tools(
        agent.tools if agent.tools else None
    )

    step_number = execution.total_steps
    total_tokens = execution.total_tokens
    steps_log: list[dict[str, Any]] = []
    start_time = time.time()

    for iteration in range(max_iterations):
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            await _finish_execution(
                db, execution, "failed", None, step_number, total_tokens
            )
            return AgentResult(
                execution_id=execution.id,
                status="failed",
                error=f"Execution timed out after {timeout_seconds}s",
                steps=steps_log,
                total_tokens=total_tokens,
            )

        step_number += 1
        llm_start = time.time()

        try:
            result = await llm_backend.chat_completion(
                messages=messages,
                model=agent.model_id or "",
                backend="vllm",
                temperature=0.3,
                max_tokens=4096,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto" if openai_tools else None,
            )
        except Exception as exc:
            await _finish_execution(
                db, execution, "failed", None, step_number, total_tokens
            )
            return AgentResult(
                execution_id=execution.id,
                status="failed",
                error=str(exc),
                steps=steps_log,
                total_tokens=total_tokens,
            )

        llm_duration_ms = int((time.time() - llm_start) * 1000)
        usage = result.get("usage", {})
        total_tokens += usage.get("total_tokens", 0)

        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content")
        tool_calls = message.get("tool_calls")

        await _persist_step(
            db, execution.id, step_number, "think", None,
            {"iteration": iteration + 1}, {"content": content}, llm_duration_ms,
        )

        if not tool_calls:
            final_text = content or ""
            await _finish_execution(
                db, execution, "completed", final_text, step_number, total_tokens
            )
            return AgentResult(
                execution_id=execution.id,
                status="completed",
                final_output=final_text,
                steps=steps_log,
                total_tokens=total_tokens,
            )

        messages.append(message)

        for tc in tool_calls:
            tc_id = tc.get("id", str(uuid.uuid4()))
            fn = tc.get("function", {})
            t_name = fn.get("name", "")
            try:
                t_args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                t_args = {}

            registered = tool_registry.get(t_name)
            needs_approval = registered.spec.requires_approval if registered else False
            step_number += 1

            if needs_approval:
                await _persist_step(
                    db, execution.id, step_number, "tool_call", t_name,
                    t_args, None, 0, requires_approval=True,
                )
                await _finish_execution(
                    db, execution, "paused", None, step_number, total_tokens
                )
                return AgentResult(
                    execution_id=execution.id,
                    status="paused",
                    steps=steps_log,
                    total_tokens=total_tokens,
                )

            t_start = time.time()
            t_result = await execute_tool(t_name, t_args, str(execution.user_id))
            t_dur = int((time.time() - t_start) * 1000)

            step_number += 1
            await _persist_step(
                db, execution.id, step_number, "tool_result", t_name,
                {"tool_call_id": tc_id}, t_result, t_dur,
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": json.dumps(t_result),
            })

    await _finish_execution(
        db, execution, "failed", None, step_number, total_tokens
    )
    return AgentResult(
        execution_id=execution.id,
        status="failed",
        error=f"Max iterations ({max_iterations}) reached after resume",
        steps=steps_log,
        total_tokens=total_tokens,
    )


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

async def _persist_step(
    db: AsyncSession,
    execution_id: uuid.UUID,
    step_number: int,
    action: str,
    tool_name: str | None,
    input_data: dict[str, Any] | None,
    output_data: dict[str, Any] | None,
    duration_ms: int,
    requires_approval: bool = False,
) -> AgentStep:
    step = AgentStep(
        execution_id=execution_id,
        step_number=step_number,
        action=action,
        tool_name=tool_name,
        input_data=input_data,
        output_data=output_data,
        duration_ms=duration_ms,
        requires_approval=requires_approval,
    )
    db.add(step)
    await db.flush()
    return step


async def _finish_execution(
    db: AsyncSession,
    execution: AgentExecution,
    status: str,
    final_output: str | None,
    total_steps: int,
    total_tokens: int,
) -> None:
    execution.status = status
    execution.final_output = final_output
    execution.total_steps = total_steps
    execution.total_tokens = total_tokens
    await db.flush()


async def _rebuild_messages(
    agent: AgentDefinition,
    execution: AgentExecution,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Rebuild the conversation messages from persisted steps."""
    messages: list[dict[str, Any]] = []

    if agent.system_prompt:
        messages.append({"role": "system", "content": agent.system_prompt})
    if execution.input_prompt:
        messages.append({"role": "user", "content": execution.input_prompt})

    # Load all steps ordered by step_number
    result = await db.execute(
        select(AgentStep)
        .where(AgentStep.execution_id == execution.id)
        .order_by(AgentStep.step_number)
    )
    steps = result.scalars().all()

    for step in steps:
        if step.action == "think" and step.output_data:
            content = step.output_data.get("content")
            if content:
                messages.append({"role": "assistant", "content": content})
        elif step.action == "tool_result" and step.output_data:
            messages.append({
                "role": "tool",
                "tool_call_id": (step.input_data or {}).get("tool_call_id", str(step.id)),
                "content": json.dumps(step.output_data),
            })

    return messages

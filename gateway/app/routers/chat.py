"""OpenAI-compatible /v1/chat/completions endpoint with streaming and persistence."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_optional_user
from app.services.conversation import (
    add_message,
    auto_title,
    build_context_window,
    create_conversation,
    get_messages,
)
from app.services.llm import llm_backend
from app.services.tool_executor import execute_tool
from app.services.tool_registry import tool_registry

router = APIRouter()
logger = logging.getLogger(__name__)

# Default tools enabled when agent_mode is on and no explicit list is provided
CHAT_DEFAULT_TOOLS = [
    "calculator",
    "rag_search",
    "file_read",
    "file_write",
    "code_analyze",
    "code_explain",
    "code_generate",
    "python_exec",
    "bash_exec",
]


class ChatMessage(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ToolFunction(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class Tool(BaseModel):
    type: str = "function"
    function: ToolFunction


class ChatCompletionRequest(BaseModel):
    model: str = ""
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    tools: list[Tool] | None = None
    tool_choice: str | None = None

    # Inference parameters
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    repeat_penalty: float | None = None

    # Extensions
    backend: str = "vllm"
    conversation_id: str | None = None
    system_prompt: str | None = None
    max_context_tokens: int = 8192

    # Agent mode extensions
    agent_mode: bool = True
    agent_tools: list[str] | None = None
    max_iterations: int = 20
    agent_timeout: float = 300.0


def _sse(event: str, data: dict | str) -> bytes:
    """Format a named SSE event."""
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n".encode()


def _sse_data(data: dict | str) -> bytes:
    """Format a default (unnamed) SSE data line."""
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"data: {payload}\n\n".encode()


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user),
):
    conv_id = None
    api_messages: list[dict[str, Any]]

    # If conversation_id provided, load history and use context windowing
    if request.conversation_id and user:
        conv_id = uuid.UUID(request.conversation_id)

        # Save the user message
        user_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        if user_msg and user_msg.content:
            await add_message(db, conv_id, role="user", content=user_msg.content)
            await auto_title(db, conv_id, user_msg.content)

        # Load full history and apply context windowing
        all_messages = await get_messages(db, conv_id)
        api_messages = build_context_window(
            all_messages,
            max_tokens=request.max_context_tokens,
            reserve_for_response=request.max_tokens,
        )
    elif not request.conversation_id and user:
        # Auto-create conversation for authenticated users
        user_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        if user_msg and user_msg.content:
            conv = await create_conversation(
                db,
                user_id=user.id,
                model_id=request.model,
                system_prompt=request.system_prompt,
            )
            conv_id = conv.id
            await add_message(db, conv_id, role="user", content=user_msg.content)
            await auto_title(db, conv_id, user_msg.content)

        api_messages = [m.model_dump(exclude_none=True) for m in request.messages]
    else:
        # Unauthenticated / stateless mode
        api_messages = [m.model_dump(exclude_none=True) for m in request.messages]

    tools_payload = None
    if request.tools:
        tools_payload = [t.model_dump() for t in request.tools]

    kwargs: dict[str, Any] = {}
    if request.tool_choice:
        kwargs["tool_choice"] = request.tool_choice
    if request.top_p is not None:
        kwargs["top_p"] = request.top_p
    if request.frequency_penalty is not None:
        kwargs["frequency_penalty"] = request.frequency_penalty
    if request.presence_penalty is not None:
        kwargs["presence_penalty"] = request.presence_penalty
    if request.repeat_penalty is not None:
        kwargs["repeat_penalty"] = request.repeat_penalty

    # Route to agent loop when agent_mode is enabled and streaming
    if request.stream and request.agent_mode:
        return StreamingResponse(
            _streaming_agent_loop(
                messages=api_messages,
                model=request.model,
                backend=request.backend,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                agent_tools=request.agent_tools,
                max_iterations=request.max_iterations,
                agent_timeout=request.agent_timeout,
                db=db,
                conv_id=conv_id,
                user_id=str(user.id) if user else None,
                extra_kwargs=kwargs,
            ),
            media_type="text/event-stream",
            headers={"X-Conversation-ID": str(conv_id) if conv_id else ""},
        )

    if request.stream:
        stream = await llm_backend.chat_completion(
            messages=api_messages,
            model=request.model,
            backend=request.backend,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools=tools_payload,
            stream=True,
            **kwargs,
        )
        # Wrap stream to capture the full response for persistence
        return StreamingResponse(
            _persist_stream(stream, db, conv_id),
            media_type="text/event-stream",
            headers={"X-Conversation-ID": str(conv_id) if conv_id else ""},
        )

    result = await llm_backend.chat_completion(
        messages=api_messages,
        model=request.model,
        backend=request.backend,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools=tools_payload,
        stream=False,
        **kwargs,
    )

    # Persist assistant response
    if conv_id and isinstance(result, dict):
        choices = result.get("choices", [])
        if choices:
            assistant_msg = choices[0].get("message", {})
            await add_message(
                db,
                conv_id,
                role="assistant",
                content=assistant_msg.get("content"),
                tool_calls=assistant_msg.get("tool_calls"),
                token_count=result.get("usage", {}).get("completion_tokens", 0),
            )

    # Include conversation_id in response for client
    if conv_id and isinstance(result, dict):
        result["_conversation_id"] = str(conv_id)

    return result


async def _streaming_agent_loop(
    *,
    messages: list[dict[str, Any]],
    model: str,
    backend: str,
    temperature: float,
    max_tokens: int,
    agent_tools: list[str] | None,
    max_iterations: int,
    agent_timeout: float,
    db: AsyncSession,
    conv_id: uuid.UUID | None,
    user_id: str | None,
    extra_kwargs: dict[str, Any],
) -> AsyncIterator[bytes]:
    """Server-side agent loop: LLM -> tool_calls -> execute -> feed back -> repeat."""

    # Resolve which tools to offer the LLM
    tool_names = agent_tools or CHAT_DEFAULT_TOOLS
    openai_tools = tool_registry.get_openai_tools(tool_names)

    # If no tools are actually registered/available, fall back to plain chat
    if not openai_tools:
        logger.warning("Agent mode requested but no tools available, falling back to plain chat")
        stream = await llm_backend.chat_completion(
            messages=messages,
            model=model,
            backend=backend,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **extra_kwargs,
        )
        async for chunk in _persist_stream(stream, db, conv_id):
            yield chunk
        return

    available_tool_names = [t["function"]["name"] for t in openai_tools]

    # Emit agent_start
    yield _sse("agent_status", {
        "type": "agent_start",
        "iteration": 1,
        "tools": available_tool_names,
    })

    loop_messages = list(messages)
    deadline = time.monotonic() + agent_timeout

    for iteration in range(1, max_iterations + 1):
        if time.monotonic() > deadline:
            yield _sse("agent_status", {
                "type": "agent_error",
                "error": "Agent timeout exceeded",
                "iterations": iteration - 1,
            })
            yield _sse_data("[DONE]")
            return

        # Call LLM with tools (non-streaming to get complete tool_calls)
        try:
            result = await llm_backend.chat_completion(
                messages=loop_messages,
                model=model,
                backend=backend,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=openai_tools,
                stream=False,
                **extra_kwargs,
            )
        except Exception as e:
            logger.exception("LLM call failed in agent loop")
            yield _sse("agent_status", {
                "type": "agent_error",
                "error": f"LLM error: {str(e)}",
                "iterations": iteration,
            })
            yield _sse_data("[DONE]")
            return

        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            # Final text response — stream it as standard SSE content tokens
            content = message.get("content", "") or ""

            # Persist assistant message
            if conv_id:
                await add_message(db, conv_id, role="assistant", content=content)

            # Stream content as delta chunks for compatibility
            if content:
                # Send in reasonable chunks to feel like streaming
                chunk_size = 20
                for i in range(0, len(content), chunk_size):
                    chunk_text = content[i : i + chunk_size]
                    yield _sse_data({
                        "choices": [{
                            "delta": {"content": chunk_text},
                            "index": 0,
                        }]
                    })
                    await asyncio.sleep(0.01)

            yield _sse("agent_status", {
                "type": "agent_done",
                "iterations": iteration,
            })
            yield _sse_data("[DONE]")
            return

        # We have tool_calls — execute them
        # Append the assistant message (with tool_calls) to loop context
        loop_messages.append({
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": tool_calls,
        })

        # Persist assistant tool-call message
        if conv_id:
            await add_message(
                db, conv_id,
                role="assistant",
                content=message.get("content"),
                tool_calls=tool_calls,
            )

        for tc in tool_calls:
            tc_id = tc.get("id", f"tc_{uuid.uuid4().hex[:8]}")
            func = tc.get("function", {})
            tool_name = func.get("name", "unknown")
            raw_args = func.get("arguments", "{}")

            # Parse arguments
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                arguments = {"raw": raw_args}

            # Emit tool_call event
            yield _sse("tool_call", {
                "id": tc_id,
                "name": tool_name,
                "arguments": arguments,
            })

            # Execute tool
            start = time.monotonic()
            try:
                tool_result = await execute_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    user_id=user_id,
                )
            except Exception as e:
                logger.exception(f"Tool execution failed: {tool_name}")
                tool_result = {
                    "success": False,
                    "output": None,
                    "error": str(e),
                    "duration_ms": (time.monotonic() - start) * 1000,
                }

            duration_ms = tool_result.get("duration_ms", 0)
            success = tool_result.get("success", False)
            output = tool_result.get("output", "")
            error = tool_result.get("error")

            # Build display output
            display_output = str(output) if success else (error or "Tool execution failed")

            # Emit tool_result event
            yield _sse("tool_result", {
                "id": tc_id,
                "name": tool_name,
                "success": success,
                "output": display_output,
                "duration_ms": round(duration_ms),
            })

            # Append tool result to messages for next LLM call
            loop_messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": display_output,
            })

            # Persist tool result message
            if conv_id:
                await add_message(
                    db, conv_id,
                    role="tool",
                    content=display_output,
                    tool_call_id=tc_id,
                )

        # Emit iteration_start for next round
        if iteration < max_iterations:
            yield _sse("agent_status", {
                "type": "iteration_start",
                "iteration": iteration + 1,
            })

    # Max iterations reached
    yield _sse("agent_status", {
        "type": "agent_error",
        "error": f"Max iterations ({max_iterations}) reached",
        "iterations": max_iterations,
    })
    yield _sse_data("[DONE]")


async def _persist_stream(
    stream: AsyncIterator[bytes],
    db: AsyncSession,
    conv_id: uuid.UUID | None,
) -> AsyncIterator[bytes]:
    """Wrap the SSE stream to capture and persist the full assistant response."""
    accumulated_content = ""
    accumulated_tool_calls: list[dict] = []

    async for chunk in stream:
        yield chunk

        # Parse the SSE data to accumulate the response
        try:
            line = chunk.decode().strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                data = json.loads(line[6:])
                delta = data.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    accumulated_content += delta["content"]
                if delta.get("tool_calls"):
                    accumulated_tool_calls.extend(delta["tool_calls"])
        except (json.JSONDecodeError, IndexError, KeyError):
            pass

    # Persist the complete assistant message
    if conv_id and (accumulated_content or accumulated_tool_calls):
        await add_message(
            db,
            conv_id,
            role="assistant",
            content=accumulated_content or None,
            tool_calls=accumulated_tool_calls or None,
        )

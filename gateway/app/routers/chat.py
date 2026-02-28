"""OpenAI-compatible /v1/chat/completions endpoint with streaming and persistence."""

import json
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

router = APIRouter()


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

    # Extensions
    backend: str = "vllm"
    conversation_id: str | None = None
    system_prompt: str | None = None
    max_context_tokens: int = 8192


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

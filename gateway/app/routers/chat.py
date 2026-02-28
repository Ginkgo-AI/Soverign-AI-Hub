"""OpenAI-compatible /v1/chat/completions endpoint with streaming support."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_optional_user
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

    # Extension: select backend
    backend: str = "vllm"

    # Extension: conversation persistence
    conversation_id: str | None = None


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user),
):
    messages = [m.model_dump(exclude_none=True) for m in request.messages]

    tools_payload = None
    if request.tools:
        tools_payload = [t.model_dump() for t in request.tools]

    kwargs: dict[str, Any] = {}
    if request.tool_choice:
        kwargs["tool_choice"] = request.tool_choice

    if request.stream:
        stream = await llm_backend.chat_completion(
            messages=messages,
            model=request.model,
            backend=request.backend,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools=tools_payload,
            stream=True,
            **kwargs,
        )
        return StreamingResponse(stream, media_type="text/event-stream")

    result = await llm_backend.chat_completion(
        messages=messages,
        model=request.model,
        backend=request.backend,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools=tools_payload,
        stream=False,
        **kwargs,
    )

    # TODO: Persist message to conversation history if conversation_id is provided

    return result

"""MCP Server endpoints — SSE transport and JSON-RPC message handling."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.mcp_server import mcp_server

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory message queues for SSE sessions
_session_queues: dict[str, asyncio.Queue] = {}


@router.get("/sse")
async def mcp_sse(request: Request, db: AsyncSession = Depends(get_db)):
    """SSE transport for MCP — establishes a long-lived connection."""
    session_id = mcp_server.create_session()
    queue: asyncio.Queue = asyncio.Queue()
    _session_queues[session_id] = queue

    async def event_stream() -> AsyncIterator[bytes]:
        # Send the endpoint URI for the client to post messages to
        yield f"event: endpoint\ndata: /mcp/messages?session_id={session_id}\n\n".encode()

        try:
            while True:
                # Wait for messages from the POST endpoint
                try:
                    response = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: message\ndata: {json.dumps(response)}\n\n".encode()
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n".encode()

                # Check if client disconnected
                if await request.is_disconnected():
                    break
        finally:
            _session_queues.pop(session_id, None)
            mcp_server.remove_session(session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/messages")
async def mcp_messages(
    request: Request,
    session_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """JSON-RPC message endpoint for MCP."""
    body = await request.json()

    if session_id is None:
        # Stateless mode — handle directly
        response = await mcp_server.handle_message(body, "stateless", db)
        return response

    # SSE mode — process and push response to the session queue
    session = mcp_server.get_session(session_id)
    if session is None:
        return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32600, "message": "Invalid session"}}

    response = await mcp_server.handle_message(body, session_id, db)

    queue = _session_queues.get(session_id)
    if queue:
        await queue.put(response)

    return {"status": "accepted"}

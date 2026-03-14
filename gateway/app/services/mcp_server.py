"""MCP Server — Model Context Protocol implementation for external tool access."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection import Collection
from app.models.skill import Skill
from app.services.tool_executor import execute_tool
from app.services.tool_registry import tool_registry

logger = logging.getLogger(__name__)


class MCPServer:
    """Handles JSON-RPC dispatch for the MCP protocol."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {"initialized": False}
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def handle_message(
        self,
        message: dict[str, Any],
        session_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Dispatch a JSON-RPC 2.0 message."""
        method = message.get("method", "")
        params = message.get("params", {})
        msg_id = message.get("id")

        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
        }

        handler = handlers.get(method)
        if handler is None:
            return _error_response(msg_id, -32601, f"Method not found: {method}")

        try:
            result = await handler(params, session_id, db)
            return _success_response(msg_id, result)
        except Exception as exc:
            logger.exception("MCP handler error: %s", method)
            return _error_response(msg_id, -32603, str(exc))

    async def _handle_initialize(
        self, params: dict, session_id: str, db: AsyncSession
    ) -> dict:
        session = self._sessions.get(session_id, {})
        session["initialized"] = True
        self._sessions[session_id] = session

        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "sovereign-ai-hub",
                "version": "0.1.0",
            },
        }

    async def _handle_tools_list(
        self, params: dict, session_id: str, db: AsyncSession
    ) -> dict:
        tools = tool_registry.list_tools()
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.parameters_schema,
                }
                for t in tools
            ]
        }

    async def _handle_tools_call(
        self, params: dict, session_id: str, db: AsyncSession
    ) -> dict:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        registered = tool_registry.get(tool_name)
        if registered is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        result = await execute_tool(
            tool_name=tool_name,
            arguments=arguments,
            user_id=None,
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": str(result.get("output", result.get("error", ""))),
                }
            ],
            "isError": not result.get("success", False),
        }

    async def _handle_resources_list(
        self, params: dict, session_id: str, db: AsyncSession
    ) -> dict:
        result = await db.execute(select(Collection).order_by(Collection.created_at))
        collections = result.scalars().all()

        return {
            "resources": [
                {
                    "uri": f"collection://{c.id}",
                    "name": c.name,
                    "description": getattr(c, "description", "") or f"Collection: {c.name}",
                    "mimeType": "application/json",
                }
                for c in collections
            ]
        }

    async def _handle_resources_read(
        self, params: dict, session_id: str, db: AsyncSession
    ) -> dict:
        uri = params.get("uri", "")
        if uri.startswith("collection://"):
            collection_id = uri.replace("collection://", "")
            result = await db.execute(
                select(Collection).where(Collection.id == uuid.UUID(collection_id))
            )
            collection = result.scalar_one_or_none()
            if collection is None:
                raise ValueError(f"Collection not found: {collection_id}")

            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": f'{{"name": "{collection.name}", "id": "{collection.id}"}}',
                    }
                ]
            }

        raise ValueError(f"Unknown resource URI: {uri}")

    async def _handle_prompts_list(
        self, params: dict, session_id: str, db: AsyncSession
    ) -> dict:
        result = await db.execute(
            select(Skill).where(Skill.enabled == True).order_by(Skill.name)  # noqa: E712
        )
        skills = result.scalars().all()

        return {
            "prompts": [
                {
                    "name": s.name,
                    "description": s.description,
                    "arguments": [
                        {"name": "query", "description": "The user's request", "required": True}
                    ],
                }
                for s in skills
            ]
        }

    async def _handle_prompts_get(
        self, params: dict, session_id: str, db: AsyncSession
    ) -> dict:
        name = params.get("name", "")
        result = await db.execute(
            select(Skill).where(Skill.name == name)
        )
        skill = result.scalar_one_or_none()
        if skill is None:
            raise ValueError(f"Prompt/skill not found: {name}")

        query = params.get("arguments", {}).get("query", "")

        return {
            "description": skill.description,
            "messages": [
                {"role": "system", "content": {"type": "text", "text": skill.system_prompt}},
                {"role": "user", "content": {"type": "text", "text": query}},
            ],
        }


def _success_response(msg_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error_response(msg_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


# Global singleton
mcp_server = MCPServer()

"""JSON-RPC 2.0 and MCP protocol schemas."""

from typing import Any

from pydantic import BaseModel, Field


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None


class MCPToolDefinition(BaseModel):
    name: str
    description: str = ""
    inputSchema: dict[str, Any] = Field(default_factory=dict)


class MCPResourceDefinition(BaseModel):
    uri: str
    name: str
    description: str = ""
    mimeType: str = "text/plain"


class MCPPromptDefinition(BaseModel):
    name: str
    description: str = ""
    arguments: list[dict[str, Any]] = Field(default_factory=list)


class MCPServerInfo(BaseModel):
    name: str = "sovereign-ai-hub"
    version: str = "0.1.0"
    protocolVersion: str = "2024-11-05"


class MCPCapabilities(BaseModel):
    tools: dict[str, Any] = Field(default_factory=lambda: {"listChanged": False})
    resources: dict[str, Any] = Field(default_factory=lambda: {"subscribe": False, "listChanged": False})
    prompts: dict[str, Any] = Field(default_factory=lambda: {"listChanged": False})

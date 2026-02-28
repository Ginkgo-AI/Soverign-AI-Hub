"""
Tool Registry -- central catalogue of tools available to agents.

Adapted from Metis_2/backend/services/tool_registry.py for the Sovereign AI Hub.

Every tool is registered with:
  - name / description
  - OpenAI function-calling parameter schema
  - category tag
  - requires_approval flag
  - an async handler callable
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    """Immutable description of a single tool."""

    name: str
    description: str
    category: str  # search, code_execution, file_ops, data_analysis, http
    parameters_schema: dict[str, Any]
    requires_approval: bool = False
    enabled: bool = True


@dataclass
class RegisteredTool:
    """A ToolSpec paired with its runtime handler."""

    spec: ToolSpec
    handler: Callable[..., Awaitable[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Registry singleton
# ---------------------------------------------------------------------------

class ToolRegistry:
    """
    Thread-safe registry of available tools.

    Tools are registered at application startup and never mutated at runtime.
    The registry provides:
      - lookup by name
      - OpenAI function-calling schema generation
      - filtering by category or approval requirement
    """

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        logger.info("ToolRegistry initialised")

    # -- registration -------------------------------------------------------

    def register(
        self,
        spec: ToolSpec,
        handler: Callable[..., Awaitable[dict[str, Any]]],
    ) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        if not callable(handler):
            raise ValueError(f"Handler for {spec.name} must be callable")
        self._tools[spec.name] = RegisteredTool(spec=spec, handler=handler)
        logger.info(
            "Registered tool: %s (category=%s, approval=%s)",
            spec.name,
            spec.category,
            spec.requires_approval,
        )

    def unregister(self, name: str) -> bool:
        return self._tools.pop(name, None) is not None

    # -- lookup -------------------------------------------------------------

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolSpec]:
        return [rt.spec for rt in self._tools.values() if rt.spec.enabled]

    def list_by_category(self, category: str) -> list[ToolSpec]:
        return [
            rt.spec
            for rt in self._tools.values()
            if rt.spec.category == category and rt.spec.enabled
        ]

    # -- OpenAI function-calling schema -------------------------------------

    def get_openai_tools(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Return tool definitions in the OpenAI ``tools`` array format.

        If *tool_names* is provided only those tools are returned; otherwise
        all enabled tools.
        """
        specs: list[ToolSpec]
        if tool_names is not None:
            specs = [
                self._tools[n].spec
                for n in tool_names
                if n in self._tools and self._tools[n].spec.enabled
            ]
        else:
            specs = self.list_tools()

        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters_schema,
                },
            }
            for s in specs
        ]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._tools)
        by_category: dict[str, int] = {}
        approval_count = 0
        for rt in self._tools.values():
            by_category[rt.spec.category] = by_category.get(rt.spec.category, 0) + 1
            if rt.spec.requires_approval:
                approval_count += 1
        return {
            "total_tools": total,
            "by_category": by_category,
            "requires_approval": approval_count,
        }


# Global singleton
tool_registry = ToolRegistry()


# ---------------------------------------------------------------------------
# Built-in tool specifications
# ---------------------------------------------------------------------------

RAG_SEARCH_SPEC = ToolSpec(
    name="rag_search",
    description="Semantic search across RAG document collections. Returns relevant text chunks.",
    category="search",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query",
            },
            "collection": {
                "type": "string",
                "description": "Optional collection name to restrict the search",
            },
            "top_k": {
                "type": "integer",
                "description": "Max results to return (default 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    requires_approval=False,
)

PYTHON_EXEC_SPEC = ToolSpec(
    name="python_exec",
    description="Execute a Python code snippet in a sandboxed subprocess. Returns stdout/stderr.",
    category="code_execution",
    parameters_schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Max execution time in seconds (default 30)",
                "default": 30,
            },
        },
        "required": ["code"],
    },
    requires_approval=True,
)

BASH_EXEC_SPEC = ToolSpec(
    name="bash_exec",
    description="Execute a shell command in a sandboxed subprocess. Returns stdout/stderr.",
    category="code_execution",
    parameters_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to run",
            },
            "timeout": {
                "type": "integer",
                "description": "Max execution time in seconds (default 30)",
                "default": 30,
            },
        },
        "required": ["command"],
    },
    requires_approval=True,
)

FILE_READ_SPEC = ToolSpec(
    name="file_read",
    description="Read the contents of a file within the workspace directory.",
    category="file_ops",
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path within the workspace",
            },
            "encoding": {
                "type": "string",
                "description": "Text encoding (default utf-8)",
                "default": "utf-8",
            },
        },
        "required": ["path"],
    },
    requires_approval=False,
)

FILE_WRITE_SPEC = ToolSpec(
    name="file_write",
    description="Write content to a file within the workspace directory.",
    category="file_ops",
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path within the workspace",
            },
            "content": {
                "type": "string",
                "description": "Text content to write",
            },
            "mode": {
                "type": "string",
                "description": "'write' (overwrite) or 'append'",
                "enum": ["write", "append"],
                "default": "write",
            },
        },
        "required": ["path", "content"],
    },
    requires_approval=True,
)

HTTP_REQUEST_SPEC = ToolSpec(
    name="http_request",
    description="Make an HTTP request to an internal API endpoint (localhost only).",
    category="http",
    parameters_schema={
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                "default": "GET",
            },
            "url": {
                "type": "string",
                "description": "URL to request (must be internal / localhost)",
            },
            "headers": {
                "type": "object",
                "description": "Optional HTTP headers",
                "additionalProperties": {"type": "string"},
            },
            "body": {
                "type": "object",
                "description": "Optional JSON body",
            },
        },
        "required": ["url"],
    },
    requires_approval=False,
)

SQL_QUERY_SPEC = ToolSpec(
    name="sql_query",
    description="Execute a read-only SQL query against the application database.",
    category="data_analysis",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL SELECT query (only read operations allowed)",
            },
            "limit": {
                "type": "integer",
                "description": "Max rows to return (default 100)",
                "default": 100,
            },
        },
        "required": ["query"],
    },
    requires_approval=True,
)

CALCULATOR_SPEC = ToolSpec(
    name="calculator",
    description="Evaluate a mathematical expression and return the numeric result.",
    category="data_analysis",
    parameters_schema={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression (e.g. '2 * (3 + 4)')",
            },
        },
        "required": ["expression"],
    },
    requires_approval=False,
)


# ---------------------------------------------------------------------------
# Convenience list of all built-in specs (handler wiring happens in
# tool_executor.py which imports this list).
# ---------------------------------------------------------------------------

BUILTIN_TOOL_SPECS: list[ToolSpec] = [
    RAG_SEARCH_SPEC,
    PYTHON_EXEC_SPEC,
    BASH_EXEC_SPEC,
    FILE_READ_SPEC,
    FILE_WRITE_SPEC,
    HTTP_REQUEST_SPEC,
    SQL_QUERY_SPEC,
    CALCULATOR_SPEC,
]

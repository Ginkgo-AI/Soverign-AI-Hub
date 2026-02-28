"""
Safe Tool Executor -- runs tool handlers with sandboxing, path scoping,
URL allowlisting, and audit logging.

Adapted from Metis_2/backend/services/safe_tool_executor.py for the
Sovereign AI Hub.

Every tool execution returns a uniform ``ToolResult`` dict:
    {"success": bool, "output": ..., "error": str|None, "duration_ms": float}

The module also wires all built-in handlers and registers them in the
global ``tool_registry``.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import math
import operator
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text as sa_text

from app.config import settings
from app.services.tool_registry import (
    BUILTIN_TOOL_SPECS,
    tool_registry,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Workspace root for file_read / file_write operations
WORKSPACE_ROOT = Path(os.environ.get("AGENT_WORKSPACE", "/tmp/agent_workspace"))

# Internal URL allowlist prefixes for http_request
_ALLOWED_URL_PREFIXES: list[str] = [
    "http://localhost",
    "http://127.0.0.1",
    f"http://{settings.vllm_host}",
    f"http://{settings.llama_cpp_host}",
    "http://gateway",
    "http://qdrant",
]

# Patterns that are always blocked in code execution
_BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"rm\s+-rf\s+/",
        r"rm\s+--no-preserve-root",
        r"mkfs\.",
        r"dd\s+if=",
        r">\s*/dev/",
        r"chmod\s+777\s+/",
        r"curl\s+.*\|\s*bash",
        r"wget\s+.*\|\s*bash",
        r":\(\)\{.*\|.*&\s*\};:",
        r"import\s+subprocess",
        r"import\s+shutil",
        r"__import__",
    ]
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    success: bool,
    output: Any = None,
    error: str | None = None,
    duration_ms: float = 0.0,
) -> dict[str, Any]:
    return {
        "success": success,
        "output": output,
        "error": error,
        "duration_ms": round(duration_ms, 2),
    }


def _check_blocked(text: str) -> str | None:
    """Return matched pattern string if blocked, else None."""
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def _resolve_workspace_path(relative: str) -> Path:
    """Resolve *relative* against WORKSPACE_ROOT and guard against traversal."""
    resolved = (WORKSPACE_ROOT / relative).resolve()
    if not str(resolved).startswith(str(WORKSPACE_ROOT.resolve())):
        raise PermissionError(f"Path escapes workspace: {relative}")
    return resolved


# ---------------------------------------------------------------------------
# Built-in tool handler implementations
# ---------------------------------------------------------------------------

async def _handle_rag_search(
    query: str,
    collection: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Placeholder RAG search -- returns stub until RAG pipeline is wired."""
    # In production this will call the Qdrant / embedding pipeline
    return {
        "query": query,
        "collection": collection,
        "top_k": top_k,
        "results": [],
        "message": "RAG search not yet connected to vector store",
    }


async def _handle_python_exec(
    code: str,
    timeout: int = 30,
) -> dict[str, Any]:
    blocked = _check_blocked(code)
    if blocked:
        raise PermissionError(f"Blocked pattern detected: {blocked}")

    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        duration = (time.time() - start) * 1000

        if proc.returncode != 0:
            return _make_result(
                success=False,
                error=stderr.decode(errors="replace")[:4096],
                duration_ms=duration,
            )
        return _make_result(
            success=True,
            output=stdout.decode(errors="replace")[:8192],
            duration_ms=duration,
        )
    except asyncio.TimeoutError:
        return _make_result(success=False, error=f"Execution timed out after {timeout}s")


async def _handle_bash_exec(
    command: str,
    timeout: int = 30,
) -> dict[str, Any]:
    blocked = _check_blocked(command)
    if blocked:
        raise PermissionError(f"Blocked pattern detected: {blocked}")

    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        duration = (time.time() - start) * 1000

        if proc.returncode != 0:
            return _make_result(
                success=False,
                output=stdout.decode(errors="replace")[:4096],
                error=stderr.decode(errors="replace")[:4096],
                duration_ms=duration,
            )
        return _make_result(
            success=True,
            output=stdout.decode(errors="replace")[:8192],
            duration_ms=duration,
        )
    except asyncio.TimeoutError:
        return _make_result(success=False, error=f"Execution timed out after {timeout}s")


async def _handle_file_read(
    path: str,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    resolved = _resolve_workspace_path(path)
    if not resolved.is_file():
        return _make_result(success=False, error=f"File not found: {path}")
    try:
        content = resolved.read_text(encoding=encoding)
        return _make_result(success=True, output=content[:32_768])
    except Exception as exc:
        return _make_result(success=False, error=str(exc))


async def _handle_file_write(
    path: str,
    content: str,
    mode: str = "write",
) -> dict[str, Any]:
    resolved = _resolve_workspace_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    try:
        if mode == "append":
            with resolved.open("a") as f:
                f.write(content)
        else:
            resolved.write_text(content)
        return _make_result(success=True, output=f"Wrote {len(content)} chars to {path}")
    except Exception as exc:
        return _make_result(success=False, error=str(exc))


async def _handle_http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Validate URL against allowlist
    if not any(url.startswith(prefix) for prefix in _ALLOWED_URL_PREFIXES):
        return _make_result(
            success=False,
            error="URL not in allowlist. Only internal endpoints permitted.",
        )

    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=body if method.upper() in ("POST", "PUT", "PATCH") else None,
            )
            duration = (time.time() - start) * 1000
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = resp.text[:8192]

            return _make_result(
                success=200 <= resp.status_code < 400,
                output={"status_code": resp.status_code, "body": resp_body},
                duration_ms=duration,
            )
        except Exception as exc:
            return _make_result(success=False, error=str(exc))


async def _handle_sql_query(
    query: str,
    limit: int = 100,
) -> dict[str, Any]:
    # Only allow SELECT statements
    stripped = query.strip().upper()
    if not stripped.startswith("SELECT"):
        return _make_result(
            success=False,
            error="Only SELECT queries are allowed.",
        )
    # Block dangerous keywords
    for kw in ("DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE"):
        if kw in stripped:
            return _make_result(
                success=False,
                error=f"Keyword {kw} is not allowed in read-only queries.",
            )

    # Add LIMIT if not present
    if "LIMIT" not in stripped:
        query = query.rstrip(";") + f" LIMIT {limit}"

    from app.database import engine

    start = time.time()
    try:
        async with engine.begin() as conn:
            result = await conn.execute(sa_text(query))
            rows = result.mappings().fetchall()
            data = [dict(r) for r in rows]
        duration = (time.time() - start) * 1000

        # Serialize datetime / uuid types
        safe_data = json.loads(json.dumps(data, default=str))

        return _make_result(
            success=True,
            output={"rows": safe_data, "row_count": len(safe_data)},
            duration_ms=duration,
        )
    except Exception as exc:
        return _make_result(success=False, error=str(exc))


# Safe math expression evaluator using AST
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_NAMES = {
    "pi": math.pi,
    "e": math.e,
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
}


def _safe_eval_expr(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval_expr(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _SAFE_NAMES:
        val = _SAFE_NAMES[node.id]
        if callable(val):
            raise ValueError(f"Use {node.id}(...) as a function call")
        return val
    if isinstance(node, ast.BinOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_fn(_safe_eval_expr(node.left), _safe_eval_expr(node.right))
    if isinstance(node, ast.UnaryOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_fn(_safe_eval_expr(node.operand))
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_NAMES:
            fn = _SAFE_NAMES[node.func.id]
            if callable(fn):
                args = [_safe_eval_expr(a) for a in node.args]
                return fn(*args)
        raise ValueError("Unsupported function call")
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


async def _handle_calculator(expression: str) -> dict[str, Any]:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval_expr(tree)
        return _make_result(success=True, output=result)
    except Exception as exc:
        return _make_result(success=False, error=f"Evaluation error: {exc}")


# ---------------------------------------------------------------------------
# Map spec names to handler functions
# ---------------------------------------------------------------------------

_HANDLER_MAP: dict[str, Any] = {
    "rag_search": _handle_rag_search,
    "python_exec": _handle_python_exec,
    "bash_exec": _handle_bash_exec,
    "file_read": _handle_file_read,
    "file_write": _handle_file_write,
    "http_request": _handle_http_request,
    "sql_query": _handle_sql_query,
    "calculator": _handle_calculator,
}


def register_builtin_tools() -> None:
    """Register all built-in tools into the global tool_registry."""
    for spec in BUILTIN_TOOL_SPECS:
        handler = _HANDLER_MAP.get(spec.name)
        if handler is None:
            logger.warning("No handler for built-in tool %s -- skipping", spec.name)
            continue
        try:
            tool_registry.register(spec, handler)
        except ValueError:
            # Already registered (e.g. tests calling this twice)
            pass
    logger.info(
        "Built-in tools registered: %s",
        [s.name for s in BUILTIN_TOOL_SPECS],
    )


# ---------------------------------------------------------------------------
# High-level execute function used by the agent executor
# ---------------------------------------------------------------------------

async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Look up *tool_name* in the registry and execute its handler.

    Returns a ``ToolResult``-shaped dict:
        {"success": bool, "output": ..., "error": str|None, "duration_ms": float}
    """
    registered = tool_registry.get(tool_name)
    if registered is None:
        return _make_result(success=False, error=f"Unknown tool: {tool_name}")

    start = time.time()
    try:
        result = await registered.handler(**arguments)
        duration = (time.time() - start) * 1000

        # If handler already returned a structured result, use it
        if isinstance(result, dict) and "success" in result:
            result.setdefault("duration_ms", round(duration, 2))
            return result

        return _make_result(success=True, output=result, duration_ms=duration)

    except PermissionError as exc:
        duration = (time.time() - start) * 1000
        logger.warning("Tool %s blocked: %s", tool_name, exc)
        return _make_result(success=False, error=f"Blocked: {exc}", duration_ms=duration)
    except Exception as exc:
        duration = (time.time() - start) * 1000
        logger.error("Tool %s failed: %s", tool_name, exc, exc_info=True)
        return _make_result(success=False, error=str(exc), duration_ms=duration)

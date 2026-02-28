"""
Code Execution Sandbox -- multi-language sandboxed code execution with sessions.

Supports Python, JavaScript (Node.js), Bash, and SQL.
Sessions maintain state between executions (session-based execution).

Note: This module uses asyncio.create_subprocess_exec (not shell exec) for
safety. All user code is written to temp files and executed via the
language runtime binary directly, preventing shell injection.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blocked patterns (safety)
# ---------------------------------------------------------------------------

_BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"rm\s+-rf\s+/",
        r"rm\s+--no-preserve-root",
        r"mkfs\.",
        r"dd\s+if=",
        r">\s*/dev/",
        r"chmod\s+777\s+/",
        r":\(\)\{.*\|.*&\s*\};:",
    ]
]


def _check_blocked(code: str) -> str | None:
    """Return matched pattern string if blocked, else None."""
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(code):
            return pattern.pattern
    return None


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class ExecutionSession:
    """Maintains state for a series of code executions."""

    def __init__(self, session_id: uuid.UUID, language: str) -> None:
        self.id = session_id
        self.language = language
        self.execution_count = 0
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"code_session_{session_id}_"))
        self.history: list[dict[str, Any]] = []

    def cleanup(self) -> None:
        """Remove temporary files for this session."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)


def _lang_ext(language: str) -> str:
    return {"python": "py", "javascript": "js", "bash": "sh", "sql": "sql"}.get(
        language, "txt"
    )


# Global session store
_sessions: dict[uuid.UUID, ExecutionSession] = {}


def get_or_create_session(
    session_id: uuid.UUID | None, language: str
) -> ExecutionSession:
    """Get an existing session or create a new one."""
    if session_id and session_id in _sessions:
        return _sessions[session_id]

    new_id = session_id or uuid.uuid4()
    session = ExecutionSession(new_id, language)
    _sessions[new_id] = session
    logger.info("Created code sandbox session %s (language=%s)", new_id, language)
    return session


def close_session(session_id: uuid.UUID) -> bool:
    """Close and clean up a session."""
    session = _sessions.pop(session_id, None)
    if session:
        session.cleanup()
        return True
    return False


# ---------------------------------------------------------------------------
# Resource limits
# ---------------------------------------------------------------------------

DEFAULT_MEMORY_LIMIT_MB = 256
DEFAULT_CPU_TIME_LIMIT_S = 30

_RESOURCE_PRELUDE_PYTHON = """
import resource, sys
# Limit memory to {mem_mb}MB
resource.setrlimit(resource.RLIMIT_AS, ({mem_bytes}, {mem_bytes}))
# Limit CPU time
resource.setrlimit(resource.RLIMIT_CPU, ({cpu_s}, {cpu_s}))
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blocked_result(pattern: str) -> dict[str, Any]:
    return {
        "stdout": "",
        "stderr": f"Blocked: dangerous pattern detected ({pattern})",
        "return_value": None,
        "exit_code": 1,
        "execution_time_ms": 0,
    }


def _timeout_result(timeout: int) -> dict[str, Any]:
    return {
        "stdout": "",
        "stderr": f"Execution timed out after {timeout}s",
        "return_value": None,
        "exit_code": 124,
        "execution_time_ms": timeout * 1000,
    }


# ---------------------------------------------------------------------------
# Language-specific executors
# Uses create_subprocess_exec with explicit binary + file path arguments
# to avoid shell injection. User code is written to a temp file on disk
# and the language runtime reads it as a script argument.
# ---------------------------------------------------------------------------

async def _run_code_file(
    binary: str,
    code_file: Path,
    session: ExecutionSession,
    timeout: int,
) -> dict[str, Any]:
    """
    Run a code file using create_subprocess_exec (no shell involvement).
    The binary is invoked directly with the code file path as argument.
    """
    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            str(code_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(session.temp_dir),
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
            },
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        elapsed = (time.time() - start) * 1000

        session.execution_count += 1
        result = {
            "stdout": stdout.decode(errors="replace")[:16384],
            "stderr": stderr.decode(errors="replace")[:8192],
            "return_value": None,
            "exit_code": proc.returncode or 0,
            "execution_time_ms": round(elapsed, 2),
        }
        session.history.append({"code": code_file.read_text(), "result": result})
        return result

    except asyncio.TimeoutError:
        return _timeout_result(timeout)


async def _execute_python(
    code: str,
    session: ExecutionSession,
    timeout: int = 30,
    memory_mb: int = DEFAULT_MEMORY_LIMIT_MB,
) -> dict[str, Any]:
    """Execute Python code in a sandboxed subprocess."""
    blocked = _check_blocked(code)
    if blocked:
        return _blocked_result(blocked)

    code_file = session.temp_dir / f"exec_{session.execution_count}.py"
    resource_limit = _RESOURCE_PRELUDE_PYTHON.format(
        mem_mb=memory_mb,
        mem_bytes=memory_mb * 1024 * 1024,
        cpu_s=timeout,
    )
    code_file.write_text(resource_limit + "\n" + code)

    return await _run_code_file("python3", code_file, session, timeout)


async def _execute_javascript(
    code: str,
    session: ExecutionSession,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute JavaScript code via Node.js."""
    blocked = _check_blocked(code)
    if blocked:
        return _blocked_result(blocked)

    code_file = session.temp_dir / f"exec_{session.execution_count}.js"
    code_file.write_text(code)

    return await _run_code_file("node", code_file, session, timeout)


async def _execute_bash(
    code: str,
    session: ExecutionSession,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute Bash script from a file (no shell injection -- file-based)."""
    blocked = _check_blocked(code)
    if blocked:
        return _blocked_result(blocked)

    code_file = session.temp_dir / f"exec_{session.execution_count}.sh"
    code_file.write_text(code)

    return await _run_code_file("/bin/bash", code_file, session, timeout)


async def _execute_sql(
    code: str,
    session: ExecutionSession,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute a read-only SQL query against the application database."""
    import json

    from sqlalchemy import text as sa_text

    stripped = code.strip().upper()
    if not stripped.startswith("SELECT"):
        return {
            "stdout": "",
            "stderr": "Only SELECT queries are allowed in the sandbox.",
            "return_value": None,
            "exit_code": 1,
            "execution_time_ms": 0,
        }

    for kw in ("DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE"):
        if kw in stripped:
            return {
                "stdout": "",
                "stderr": f"Keyword {kw} is not allowed in read-only queries.",
                "return_value": None,
                "exit_code": 1,
                "execution_time_ms": 0,
            }

    from app.database import engine

    start = time.time()
    try:
        async with engine.begin() as conn:
            result = await asyncio.wait_for(
                conn.execute(sa_text(code)),
                timeout=timeout,
            )
            rows = result.mappings().fetchall()
            data = [dict(r) for r in rows[:500]]

        safe_data = json.loads(json.dumps(data, default=str))
        elapsed = (time.time() - start) * 1000

        output = json.dumps(safe_data, indent=2)
        session.execution_count += 1
        exec_result = {
            "stdout": output[:16384],
            "stderr": "",
            "return_value": f"{len(safe_data)} rows returned",
            "exit_code": 0,
            "execution_time_ms": round(elapsed, 2),
        }
        session.history.append({"code": code, "result": exec_result})
        return exec_result

    except asyncio.TimeoutError:
        return _timeout_result(timeout)
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return {
            "stdout": "",
            "stderr": str(exc)[:4096],
            "return_value": None,
            "exit_code": 1,
            "execution_time_ms": round(elapsed, 2),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_EXECUTORS = {
    "python": _execute_python,
    "javascript": _execute_javascript,
    "bash": _execute_bash,
    "sql": _execute_sql,
}


async def execute_code(
    code: str,
    language: str = "python",
    session_id: uuid.UUID | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Execute code in the specified language within a sandboxed session.

    Returns dict with stdout, stderr, return_value, exit_code, execution_time_ms.
    """
    executor = _EXECUTORS.get(language)
    if executor is None:
        return {
            "stdout": "",
            "stderr": f"Unsupported language: {language}. Supported: {list(_EXECUTORS.keys())}",
            "return_value": None,
            "exit_code": 1,
            "execution_time_ms": 0,
        }

    session = get_or_create_session(session_id, language)
    return await executor(code, session, timeout)

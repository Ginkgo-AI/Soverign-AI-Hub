"""
Code Workspace Service -- manages project workspaces on disk.

Provides workspace CRUD, file operations, indexing, and basic git support.
Workspaces are stored under /data/workspaces/{user_id}/{workspace_id}/.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tarfile
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from app.schemas.code import FileContent, FileTreeNode

logger = logging.getLogger(__name__)

WORKSPACE_BASE = Path(os.environ.get("CODE_WORKSPACE_BASE", "/data/workspaces"))

# Language detection by file extension
_EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".md": "markdown",
    ".rst": "rst",
    ".txt": "text",
    ".r": "r",
    ".R": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".dockerfile": "dockerfile",
    ".tf": "terraform",
    ".proto": "protobuf",
}


def detect_language(filename: str) -> str | None:
    """Detect programming language from file extension."""
    ext = Path(filename).suffix.lower()
    if ext in _EXTENSION_LANGUAGE_MAP:
        return _EXTENSION_LANGUAGE_MAP[ext]
    # Check basename for special files
    basename = Path(filename).name.lower()
    if basename in ("dockerfile", "makefile", "cmakelists.txt"):
        return basename.lower()
    if basename in (".gitignore", ".dockerignore", ".env"):
        return "text"
    return None


def _safe_resolve(workspace_root: Path, relative_path: str) -> Path:
    """Resolve a path within workspace, preventing directory traversal."""
    resolved = (workspace_root / relative_path).resolve()
    ws_resolved = workspace_root.resolve()
    if not str(resolved).startswith(str(ws_resolved)):
        raise PermissionError(f"Path escapes workspace: {relative_path}")
    return resolved


def get_workspace_path(user_id: str | uuid.UUID, workspace_id: str | uuid.UUID) -> Path:
    """Return the filesystem path for a workspace."""
    return WORKSPACE_BASE / str(user_id) / str(workspace_id)


def create_workspace_dir(user_id: str | uuid.UUID, workspace_id: str | uuid.UUID) -> Path:
    """Create workspace directory and return its path."""
    ws_path = get_workspace_path(user_id, workspace_id)
    ws_path.mkdir(parents=True, exist_ok=True)
    logger.info("Created workspace directory: %s", ws_path)
    return ws_path


def delete_workspace_dir(workspace_path: str | Path) -> None:
    """Delete a workspace directory and all contents."""
    p = Path(workspace_path)
    if p.exists():
        shutil.rmtree(p)
        logger.info("Deleted workspace directory: %s", p)


def build_file_tree(
    root: Path,
    relative_root: str = "",
    max_depth: int = 10,
    _depth: int = 0,
) -> list[FileTreeNode]:
    """Recursively build a file tree structure for a workspace."""
    if _depth > max_depth:
        return []

    nodes: list[FileTreeNode] = []
    try:
        entries = sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return nodes

    for entry in entries:
        # Skip hidden/system directories
        if entry.name.startswith(".") and entry.is_dir() and entry.name != ".git":
            continue
        if entry.name in ("__pycache__", "node_modules", ".venv", "venv"):
            continue

        rel_path = f"{relative_root}/{entry.name}" if relative_root else entry.name

        if entry.is_dir():
            children = build_file_tree(entry, rel_path, max_depth, _depth + 1)
            nodes.append(
                FileTreeNode(
                    name=entry.name,
                    path=rel_path,
                    is_dir=True,
                    children=children,
                )
            )
        else:
            size = entry.stat().st_size if entry.exists() else 0
            lang = detect_language(entry.name)
            line_count = None
            if size < 1_000_000:  # Only count lines for files < 1MB
                try:
                    line_count = len(entry.read_text(errors="replace").splitlines())
                except Exception:
                    pass

            nodes.append(
                FileTreeNode(
                    name=entry.name,
                    path=rel_path,
                    is_dir=False,
                    size=size,
                    language=lang,
                    line_count=line_count,
                )
            )

    return nodes


def read_file(workspace_path: Path, relative_path: str) -> FileContent:
    """Read a file from a workspace."""
    resolved = _safe_resolve(workspace_path, relative_path)
    if not resolved.is_file():
        raise FileNotFoundError(f"File not found: {relative_path}")

    content = resolved.read_text(errors="replace")
    lang = detect_language(resolved.name)
    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

    return FileContent(
        path=relative_path,
        content=content,
        language=lang,
        size=resolved.stat().st_size,
        line_count=lines,
    )


def write_file(workspace_path: Path, relative_path: str, content: str) -> FileContent:
    """Write content to a file in a workspace."""
    resolved = _safe_resolve(workspace_path, relative_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content)

    lang = detect_language(resolved.name)
    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

    return FileContent(
        path=relative_path,
        content=content,
        language=lang,
        size=len(content.encode()),
        line_count=lines,
    )


def delete_file(workspace_path: Path, relative_path: str) -> None:
    """Delete a file or directory from a workspace."""
    resolved = _safe_resolve(workspace_path, relative_path)
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.is_file():
        resolved.unlink()
    else:
        raise FileNotFoundError(f"Not found: {relative_path}")


def extract_upload(workspace_path: Path, file_bytes: bytes, filename: str) -> int:
    """
    Extract an uploaded archive (zip or tar) into a workspace.
    Returns the number of files extracted.
    """
    file_count = 0
    ws_resolved = workspace_path.resolve()

    if filename.endswith(".zip"):
        with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                target = (workspace_path / info.filename).resolve()
                if not str(target).startswith(str(ws_resolved)):
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                file_count += 1

    elif filename.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2")):
        mode = "r:gz" if filename.endswith((".tar.gz", ".tgz")) else (
            "r:bz2" if filename.endswith(".tar.bz2") else "r:"
        )
        with tarfile.open(fileobj=BytesIO(file_bytes), mode=mode) as tf:
            for member in tf.getmembers():
                if member.isdir():
                    continue
                target = (workspace_path / member.name).resolve()
                if not str(target).startswith(str(ws_resolved)):
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = tf.extractfile(member)
                if extracted:
                    target.write_bytes(extracted.read())
                    file_count += 1
    else:
        raise ValueError(f"Unsupported archive format: {filename}")

    logger.info("Extracted %d files from %s into %s", file_count, filename, workspace_path)
    return file_count


def build_manifest(workspace_path: Path) -> dict[str, Any]:
    """Build a workspace manifest with file stats."""
    manifest: dict[str, Any] = {
        "total_files": 0,
        "total_size": 0,
        "languages": {},
        "files": [],
    }

    ws_resolved = workspace_path.resolve()
    for filepath in ws_resolved.rglob("*"):
        if filepath.is_dir():
            continue
        parts = filepath.relative_to(ws_resolved).parts
        if any(p.startswith(".") for p in parts):
            continue
        if any(p in ("__pycache__", "node_modules", ".venv") for p in parts):
            continue

        rel = str(filepath.relative_to(ws_resolved))
        size = filepath.stat().st_size
        lang = detect_language(filepath.name) or "unknown"

        manifest["total_files"] += 1
        manifest["total_size"] += size
        manifest["languages"][lang] = manifest["languages"].get(lang, 0) + 1
        manifest["files"].append({
            "path": rel,
            "size": size,
            "language": lang,
        })

    return manifest


# ---------------------------------------------------------------------------
# Git operations within workspace
# ---------------------------------------------------------------------------


async def _git_run(workspace_path: Path, *args: str, timeout: int = 30) -> dict[str, str]:
    """Run a git command in the workspace directory."""
    cmd = ["git", "-C", str(workspace_path)] + list(args)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "stdout": stdout.decode(errors="replace").strip(),
            "stderr": stderr.decode(errors="replace").strip(),
            "returncode": str(proc.returncode),
        }
    except asyncio.TimeoutError:
        return {"stdout": "", "stderr": "Git command timed out", "returncode": "1"}


async def git_init(workspace_path: Path) -> dict[str, str]:
    """Initialize a git repository in the workspace."""
    return await _git_run(workspace_path, "init")


async def git_status(workspace_path: Path) -> dict[str, str]:
    """Get git status of the workspace."""
    return await _git_run(workspace_path, "status", "--porcelain")


async def git_diff(workspace_path: Path, staged: bool = False) -> dict[str, str]:
    """Get git diff of the workspace."""
    args = ["diff"]
    if staged:
        args.append("--staged")
    return await _git_run(workspace_path, *args)


async def git_log(workspace_path: Path, count: int = 20) -> dict[str, str]:
    """Get git log of the workspace."""
    return await _git_run(
        workspace_path,
        "log",
        f"--max-count={count}",
        "--oneline",
        "--decorate",
    )


async def git_commit(
    workspace_path: Path,
    message: str,
    add_all: bool = True,
) -> dict[str, str]:
    """Commit changes in the workspace."""
    if add_all:
        await _git_run(workspace_path, "add", "-A")
    return await _git_run(workspace_path, "commit", "-m", message)


async def git_branch(workspace_path: Path) -> dict[str, str]:
    """List git branches."""
    return await _git_run(workspace_path, "branch", "-a")

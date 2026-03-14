"""Plugin manager — loads/unloads dynamic tools from the database."""

from __future__ import annotations

import ast
import logging
import types
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugin import PluginTool
from app.services.tool_registry import ToolSpec, tool_registry

logger = logging.getLogger(__name__)

# Imports blocked inside plugin handler code for security
BLOCKED_IMPORTS = {"os", "sys", "subprocess", "shutil", "socket", "ctypes", "importlib"}


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Validate a plugin manifest and return a list of errors (empty = valid)."""
    errors: list[str] = []
    if not manifest.get("name"):
        errors.append("Manifest must include 'name'")
    if not isinstance(manifest.get("parameters_schema", {}), dict):
        errors.append("parameters_schema must be a dict")
    return errors


def _check_blocked_imports(source: str) -> list[str]:
    """Return list of blocked imports found in source code via AST analysis."""
    violations: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        violations.append("Source code has syntax errors")
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in BLOCKED_IMPORTS:
                    violations.append(f"Blocked import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top in BLOCKED_IMPORTS:
                    violations.append(f"Blocked import: {node.module}")
    return violations


def compile_handler(name: str, source: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    """
    Compile plugin handler source into an async callable.

    The source must define an async function called `handle(**kwargs)`.
    """
    violations = _check_blocked_imports(source)
    if violations:
        raise ValueError(f"Plugin '{name}' contains blocked imports: {violations}")

    module = types.ModuleType(f"plugin_{name}")
    # Provide safe standard-library modules
    module.__dict__["json"] = __import__("json")
    module.__dict__["math"] = __import__("math")
    module.__dict__["re"] = __import__("re")
    module.__dict__["datetime"] = __import__("datetime")

    code = compile(source, f"<plugin:{name}>", "exec")
    module_globals = module.__dict__
    # Execute in the module namespace (controlled context — this is intentional
    # for the plugin system, not arbitrary user input)
    _exec_in_module(code, module_globals)

    handler = getattr(module, "handle", None)
    if handler is None or not callable(handler):
        raise ValueError(f"Plugin '{name}' must define an async function called 'handle'")

    return handler


def _exec_in_module(code: Any, globals_dict: dict) -> None:
    """Execute compiled code in the given module globals dict.

    This is the controlled execution path for admin-installed plugins.
    Only administrators can install plugins, and source is validated
    via AST analysis before reaching this point.
    """
    exec(code, globals_dict)  # noqa: S102 — intentional, admin-only plugin loading


def load_plugin(plugin: PluginTool) -> None:
    """Compile and register a single plugin tool."""
    if tool_registry.get(plugin.name) is not None:
        logger.warning("Plugin '%s' already registered, skipping", plugin.name)
        return

    handler = compile_handler(plugin.name, plugin.handler_module)

    spec = ToolSpec(
        name=plugin.name,
        description=plugin.description,
        category=plugin.category,
        parameters_schema=plugin.parameters_schema,
        requires_approval=plugin.requires_approval,
        enabled=True,
        is_builtin=False,
    )
    tool_registry.register(spec, handler)
    logger.info("Loaded plugin tool: %s v%s", plugin.name, plugin.version)


def unload_plugin(name: str) -> bool:
    """Unregister a plugin tool (refuses to unload built-in tools)."""
    registered = tool_registry.get(name)
    if registered is None:
        return False
    if getattr(registered.spec, "is_builtin", True):
        logger.warning("Cannot unload built-in tool: %s", name)
        return False
    return tool_registry.unregister(name)


async def load_all_plugins(db: AsyncSession) -> int:
    """Load all enabled plugins from the database at startup."""
    result = await db.execute(
        select(PluginTool).where(PluginTool.enabled == True)  # noqa: E712
    )
    plugins = result.scalars().all()
    loaded = 0
    for plugin in plugins:
        try:
            load_plugin(plugin)
            loaded += 1
        except Exception:
            logger.exception("Failed to load plugin: %s", plugin.name)
    logger.info("Loaded %d/%d enabled plugins", loaded, len(plugins))
    return loaded

"""Role-Based Access Control service for Phase 6.

Defines a permissions matrix and provides FastAPI dependencies for
role/permission enforcement.
"""

from __future__ import annotations

from functools import wraps
from typing import Any

from fastapi import Depends, HTTPException, status

from app.middleware.auth import get_current_user

# ---------------------------------------------------------------------------
# Permissions matrix
# ---------------------------------------------------------------------------
# Structure:  role -> resource_type -> [allowed_actions]
PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "admin": {
        "*": ["*"],  # full access
    },
    "manager": {
        "collections": ["list", "read", "create", "update", "delete"],
        "documents": ["list", "read", "create", "update", "delete"],
        "agents": ["list", "read", "create", "update", "delete", "execute"],
        "users": ["list", "read", "update"],  # users in their org
        "conversations": ["list", "read", "create", "delete"],
        "chat": ["create", "read"],
        "search": ["execute"],
        "models": ["list", "read"],
        "system_prompts": ["list", "read", "create", "update", "delete"],
        "audio": ["create", "read"],
        "images": ["create", "read", "list"],
        "code": ["create", "read", "execute"],
        "audit": ["list", "read"],
    },
    "analyst": {
        "collections": ["list", "read"],
        "documents": ["list", "read"],
        "agents": ["list", "read", "execute"],
        "conversations": ["list", "read", "create"],
        "chat": ["create", "read"],
        "search": ["execute"],
        "models": ["list", "read"],
        "system_prompts": ["list", "read"],
        "audio": ["create", "read"],
        "images": ["create", "read", "list"],
        "code": ["create", "read", "execute"],
    },
    "viewer": {
        "collections": ["list", "read"],
        "documents": ["list", "read"],
        "agents": ["list", "read"],
        "conversations": ["list", "read"],
        "chat": ["read"],
        "search": ["execute"],
        "models": ["list", "read"],
        "system_prompts": ["list", "read"],
        "images": ["list", "read"],
        "code": ["read"],
    },
}

ROLE_HIERARCHY = {"admin": 4, "manager": 3, "analyst": 2, "viewer": 1}


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------
def check_permission(user: Any, resource_type: str, action: str) -> bool:
    """Return True if *user.role* has permission to perform *action* on *resource_type*."""
    role = getattr(user, "role", "viewer")
    role_perms = PERMISSIONS.get(role, {})

    # Wildcard (admin)
    if "*" in role_perms and "*" in role_perms["*"]:
        return True

    allowed_actions = role_perms.get(resource_type, [])
    return action in allowed_actions or "*" in allowed_actions


def has_minimum_role(user_role: str, required_role: str) -> bool:
    """Check if *user_role* meets or exceeds *required_role* in the hierarchy."""
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 99)


def get_role_permissions(role: str) -> dict[str, list[str]]:
    """Return the full permissions dict for *role*."""
    return PERMISSIONS.get(role, {})


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
def require_role(role: str):
    """FastAPI dependency: raises 403 if the current user's role is below *role*."""

    async def _checker(user=Depends(get_current_user)):
        if not has_minimum_role(user.role, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{role}' or higher. Current role: '{user.role}'.",
            )
        return user

    return _checker


def require_permission(resource_type: str, action: str):
    """FastAPI dependency: raises 403 if the user lacks a specific permission."""

    async def _checker(user=Depends(get_current_user)):
        if not check_permission(user, resource_type, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} on {resource_type}.",
            )
        return user

    return _checker

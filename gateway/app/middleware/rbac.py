"""RBAC middleware / FastAPI dependency for Phase 6.

Provides ``RoleChecker`` — a reusable class-based dependency that validates
the authenticated user's role against a minimum required role.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.middleware.auth import get_current_user
from app.services.rbac import ROLE_HIERARCHY


class RoleChecker:
    """FastAPI dependency that validates ``user.role`` against a required role.

    Usage::

        admin_only = RoleChecker("admin")

        @router.get("/secret", dependencies=[Depends(admin_only)])
        async def secret_endpoint(): ...
    """

    def __init__(self, required_role: str) -> None:
        self.required_role = required_role

    async def __call__(self, user=Depends(get_current_user)):
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        required_level = ROLE_HIERARCHY.get(self.required_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{self.required_role}' or higher required. Your role: '{user.role}'.",
            )
        return user

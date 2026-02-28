"""Optional Keycloak OIDC integration for Phase 6.

When ``KEYCLOAK_URL`` is configured the system validates incoming tokens
against the Keycloak server.  Otherwise, it falls back to built-in JWT auth.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger("sovereign.keycloak")
security = HTTPBearer(auto_error=False)


def keycloak_enabled() -> bool:
    """Return ``True`` if Keycloak integration is configured."""
    return bool(settings.keycloak_url and settings.keycloak_realm)


class KeycloakClient:
    """Validates OIDC tokens against a Keycloak server."""

    def __init__(self) -> None:
        self._base = settings.keycloak_url.rstrip("/") if settings.keycloak_url else ""
        self._realm = settings.keycloak_realm
        self._client_id = settings.keycloak_client_id
        self._client_secret = settings.keycloak_client_secret
        self._certs_cache: dict[str, Any] | None = None

    @property
    def _realm_url(self) -> str:
        return f"{self._base}/realms/{self._realm}"

    @property
    def _token_introspect_url(self) -> str:
        return f"{self._realm_url}/protocol/openid-connect/token/introspect"

    @property
    def _userinfo_url(self) -> str:
        return f"{self._realm_url}/protocol/openid-connect/userinfo"

    @property
    def _certs_url(self) -> str:
        return f"{self._realm_url}/protocol/openid-connect/certs"

    # -- Token introspection ------------------------------------------------
    async def introspect_token(self, token: str) -> dict[str, Any]:
        """Call the Keycloak token introspection endpoint."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._token_introspect_url,
                data={
                    "token": token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Validate an OIDC access token. Returns the introspection payload."""
        data = await self.introspect_token(token)
        if not data.get("active"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is not active (Keycloak introspection).",
            )
        return data

    # -- User info ----------------------------------------------------------
    async def get_userinfo(self, token: str) -> dict[str, Any]:
        """Fetch user info from Keycloak."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                self._userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    # -- User sync ----------------------------------------------------------
    async def sync_user(self, token_data: dict[str, Any], db: AsyncSession) -> Any:
        """Create or update a local User record from Keycloak token data."""
        from app.models.user import User

        sub = token_data.get("sub") or token_data.get("preferred_username")
        email = token_data.get("email", f"{sub}@keycloak")
        name = token_data.get("name") or token_data.get("preferred_username") or sub

        # Map Keycloak realm roles to local roles
        realm_roles = (
            token_data.get("realm_access", {}).get("roles", [])
        )
        role = "viewer"
        for r in ("admin", "manager", "analyst"):
            if r in realm_roles:
                role = r
                break

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                name=name,
                hashed_password="keycloak-managed",
                role=role,
                is_active=True,
            )
            db.add(user)
            await db.flush()
        else:
            user.name = name
            user.role = role
            await db.flush()
        return user


# Singleton
_keycloak_client: KeycloakClient | None = None


def get_keycloak_client() -> KeycloakClient:
    global _keycloak_client
    if _keycloak_client is None:
        _keycloak_client = KeycloakClient()
    return _keycloak_client


# ---------------------------------------------------------------------------
# FastAPI dependency — Keycloak-aware auth
# ---------------------------------------------------------------------------
async def get_current_user_keycloak(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Validate via Keycloak if configured, otherwise fall back to built-in JWT."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = credentials.credentials

    if keycloak_enabled():
        kc = get_keycloak_client()
        try:
            token_data = await kc.validate_token(token)
            user = await kc.sync_user(token_data, db)
            await db.commit()
            return user
        except HTTPException:
            raise
        except Exception:
            logger.exception("Keycloak validation failed, rejecting token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Keycloak authentication failed.",
            )
    else:
        # Fall back to built-in JWT
        from app.middleware.auth import get_current_user

        return await get_current_user(credentials, db)

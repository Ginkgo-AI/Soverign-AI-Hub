"""Admin endpoints: users, roles, audit log, security config, compliance.

All endpoints require the ``admin`` role unless otherwise noted.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.security import (
    AuditLogEntry,
    AuditLogExport,
    AuditLogQuery,
    AuditStats,
    ComplianceReport,
    SecurityConfig,
    SecurityConfigUpdate,
    UserActiveUpdate,
    UserRoleUpdate,
)
from app.services.audit import AuditService
from app.services.compliance import generate_compliance_report
from app.services.rbac import get_role_permissions, require_role

router = APIRouter()

# All admin endpoints require admin role
admin_dep = Depends(require_role("admin"))


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@router.get("/users", response_model=dict)
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin=admin_dep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
):
    """List all users with roles and status."""
    stmt = select(User).order_by(User.created_at.desc())
    count_stmt = select(func.count(User.id))

    if search:
        like = f"%{search}%"
        stmt = stmt.where(User.email.ilike(like) | User.name.ilike(like))
        count_stmt = count_stmt.where(User.email.ilike(like) | User.name.ilike(like))

    total = (await db.execute(count_stmt)).scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(stmt.offset(offset).limit(page_size))
    users = result.scalars().all()

    return {
        "users": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin=admin_dep,
):
    """Update a user's role (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = body.role
    await db.flush()

    await AuditService.log_event(
        action="USER_ROLE_CHANGE",
        resource_type="users",
        resource_id=str(user_id),
        user_id=admin.id,
        details={"new_role": body.role},
    )

    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/active", response_model=UserResponse)
async def update_user_active(
    user_id: uuid.UUID,
    body: UserActiveUpdate,
    db: AsyncSession = Depends(get_db),
    admin=admin_dep,
):
    """Enable or disable a user account (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = body.is_active
    await db.flush()

    await AuditService.log_event(
        action="USER_STATUS_CHANGE",
        resource_type="users",
        resource_id=str(user_id),
        user_id=admin.id,
        details={"is_active": body.is_active},
    )

    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
@router.get("/audit")
async def query_audit_log(
    db: AsyncSession = Depends(get_db),
    admin=admin_dep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    classification_level: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    search: str | None = Query(None),
):
    """Query the audit log with filtering and pagination."""
    result = await AuditService.query_logs(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        classification_level=classification_level,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    result["entries"] = [
        AuditLogEntry.model_validate(e) for e in result["entries"]
    ]
    return result


@router.get("/audit/export")
async def export_audit_log(
    db: AsyncSession = Depends(get_db),
    admin=admin_dep,
    format: str = Query("json", pattern="^(json|csv|syslog)$"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    """Export audit log in JSON, CSV, or syslog format."""
    content = await AuditService.export_logs(
        db, format=format, date_from=date_from, date_to=date_to
    )
    media_types = {
        "json": "application/json",
        "csv": "text/csv",
        "syslog": "text/plain",
    }
    return PlainTextResponse(
        content=content,
        media_type=media_types.get(format, "text/plain"),
        headers={"Content-Disposition": f'attachment; filename="audit_log.{format}"'},
    )


@router.get("/audit/stats", response_model=AuditStats)
async def audit_stats(
    db: AsyncSession = Depends(get_db),
    admin=admin_dep,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    """Get aggregate audit statistics for the dashboard."""
    return await AuditService.get_stats(db, date_from=date_from, date_to=date_to)


# ---------------------------------------------------------------------------
# Security configuration
# ---------------------------------------------------------------------------
@router.get("/security/config", response_model=SecurityConfig)
async def get_security_config(admin=admin_dep):
    """Return the current security configuration."""
    levels = [l.strip() for l in settings.classification_levels.split(",") if l.strip()]
    return SecurityConfig(
        airgap_mode=settings.airgap_mode,
        classification_levels=levels,
        session_timeout_minutes=settings.session_timeout_minutes,
        max_concurrent_sessions=settings.max_concurrent_sessions,
        encryption_enabled=bool(
            settings.encryption_key
            and settings.encryption_key != "dev-secret-change-in-production"
        )
        or bool(settings.gateway_secret_key != "dev-secret-change-in-production"),
        audit_retention_days=settings.audit_retention_days,
        siem_endpoint=settings.siem_endpoint,
        keycloak_enabled=bool(settings.keycloak_url and settings.keycloak_realm),
    )


@router.put("/security/config", response_model=SecurityConfig)
async def update_security_config(
    body: SecurityConfigUpdate,
    admin=admin_dep,
):
    """Update mutable security configuration values.

    Note: some settings (airgap_mode, encryption keys) require a restart
    to take full effect.  This endpoint updates the in-memory values for
    the running process.
    """
    if body.airgap_mode is not None:
        settings.airgap_mode = body.airgap_mode
    if body.session_timeout_minutes is not None:
        settings.session_timeout_minutes = body.session_timeout_minutes
    if body.max_concurrent_sessions is not None:
        settings.max_concurrent_sessions = body.max_concurrent_sessions
    if body.audit_retention_days is not None:
        settings.audit_retention_days = body.audit_retention_days
    if body.siem_endpoint is not None:
        settings.siem_endpoint = body.siem_endpoint

    await AuditService.log_event(
        action="SECURITY_CONFIG_UPDATE",
        resource_type="security",
        user_id=admin.id,
        details=body.model_dump(exclude_none=True),
    )

    return await get_security_config(admin)


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------
@router.get("/compliance/report", response_model=ComplianceReport)
async def compliance_report(admin=admin_dep):
    """Generate a NIST 800-53 compliance report from actual system state."""
    return generate_compliance_report()


# ---------------------------------------------------------------------------
# System health (detailed)
# ---------------------------------------------------------------------------
@router.get("/system/health")
async def system_health(admin=admin_dep):
    """Detailed system health check for all services."""
    checks: dict[str, str] = {}

    # Postgres
    try:
        from app.database import engine

        async with engine.begin() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(f"redis://{settings.redis_host}:{settings.redis_port}")
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Qdrant
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"http://{settings.qdrant_host}:{settings.qdrant_port}/healthz")
            checks["qdrant"] = "ok" if resp.status_code == 200 else f"status {resp.status_code}"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"

    # LLM backends
    from app.services.llm import llm_backend

    for backend in ("vllm", "llama-cpp"):
        try:
            ok = await llm_backend.health_check(backend)
            checks[backend] = "ok" if ok else "unavailable"
        except Exception as e:
            checks[backend] = f"error: {e}"

    # Air-gap status
    checks["airgap_mode"] = "enabled" if settings.airgap_mode else "disabled"

    # Keycloak
    if settings.keycloak_url:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{settings.keycloak_url}/health")
                checks["keycloak"] = "ok" if resp.status_code == 200 else f"status {resp.status_code}"
        except Exception as e:
            checks["keycloak"] = f"error: {e}"
    else:
        checks["keycloak"] = "not_configured"

    all_ok = checks.get("postgres") == "ok"
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

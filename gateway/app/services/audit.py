"""Full audit service for Phase 6.

Provides ``AuditService`` with methods to log, query, export and analyse
audit events persisted in the ``audit_log`` PostgreSQL table.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.audit import AuditLog

logger = logging.getLogger("sovereign.audit")

# Sensitive field names that should be redacted from request bodies
_SENSITIVE_FIELDS = {
    "password",
    "hashed_password",
    "secret",
    "token",
    "access_token",
    "api_key",
    "authorization",
    "credit_card",
    "ssn",
}

# ---------------------------------------------------------------------------
# In-memory write buffer for batched DB writes
# ---------------------------------------------------------------------------
_buffer: list[dict[str, Any]] = []
_buffer_lock = asyncio.Lock()
_FLUSH_THRESHOLD = 20  # flush after N records
_FLUSH_INTERVAL_S = 5.0  # or after N seconds
_last_flush: float = time.monotonic()


def _redact(obj: Any, depth: int = 0) -> Any:
    """Recursively redact sensitive fields from a dict/JSON-like structure."""
    if depth > 5:
        return "..."
    if isinstance(obj, dict):
        return {
            k: ("***REDACTED***" if k.lower() in _SENSITIVE_FIELDS else _redact(v, depth + 1))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(v, depth + 1) for v in obj[:20]]
    return obj


def _summarise_body(body: bytes | str | None, max_len: int = 500) -> str | None:
    """Return a redacted summary of a request body (first *max_len* chars)."""
    if not body:
        return None
    text_body = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    try:
        parsed = json.loads(text_body)
        redacted = _redact(parsed)
        serialized = json.dumps(redacted, default=str)
    except (json.JSONDecodeError, TypeError):
        serialized = text_body
    return serialized[:max_len]


# ---------------------------------------------------------------------------
# Buffer flush
# ---------------------------------------------------------------------------
async def _flush_buffer() -> None:
    """Persist buffered audit records to PostgreSQL."""
    global _last_flush
    async with _buffer_lock:
        if not _buffer:
            return
        records = list(_buffer)
        _buffer.clear()
        _last_flush = time.monotonic()

    try:
        async with async_session() as db:
            for rec in records:
                db.add(AuditLog(**rec))
            await db.commit()
    except Exception:
        logger.exception("Failed to flush %d audit records to DB", len(records))


async def _maybe_flush() -> None:
    """Flush if threshold or interval exceeded."""
    should_flush = len(_buffer) >= _FLUSH_THRESHOLD or (
        time.monotonic() - _last_flush > _FLUSH_INTERVAL_S and _buffer
    )
    if should_flush:
        await _flush_buffer()


# ---------------------------------------------------------------------------
# Public write helpers (used by middleware and application code)
# ---------------------------------------------------------------------------
async def buffer_audit_record(record: dict[str, Any]) -> None:
    """Add an audit record to the in-memory buffer (non-blocking)."""
    async with _buffer_lock:
        _buffer.append(record)
    # Schedule flush check without blocking the caller
    asyncio.ensure_future(_maybe_flush())


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------
class AuditService:
    """High-level audit service used by routers and application code."""

    # -- Direct write (bypasses buffer for critical events) -----------------
    @staticmethod
    async def log_event(
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        classification_level: str = "UNCLASSIFIED",
        ip_address: str | None = None,
        model_id: str | None = None,
        token_count: int = 0,
    ) -> None:
        """Write an audit event directly to the database."""
        try:
            async with async_session() as db:
                entry = AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    request_summary=json.dumps(details, default=str)[:500] if details else None,
                    classification_level=classification_level,
                    ip_address=ip_address,
                    model_id=model_id,
                    token_count=token_count,
                    metadata_=details,
                )
                db.add(entry)
                await db.commit()
        except Exception:
            logger.exception("Failed to write audit event %s", action)

    # -- Query -------------------------------------------------------------
    @staticmethod
    async def query_logs(
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 50,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        classification_level: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """Paginated query with filtering."""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
        count_stmt = select(func.count(AuditLog.id))

        conditions = []
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if classification_level:
            conditions.append(AuditLog.classification_level == classification_level)
        if date_from:
            conditions.append(AuditLog.timestamp >= date_from)
        if date_to:
            conditions.append(AuditLog.timestamp <= date_to)
        if search:
            conditions.append(
                AuditLog.request_summary.ilike(f"%{search}%")
                | AuditLog.resource_id.ilike(f"%{search}%")
            )

        for cond in conditions:
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        total = (await db.execute(count_stmt)).scalar() or 0
        offset = (page - 1) * page_size
        result = await db.execute(stmt.offset(offset).limit(page_size))
        entries = result.scalars().all()

        return {
            "entries": entries,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if page_size else 0,
        }

    # -- Export ------------------------------------------------------------
    @staticmethod
    async def export_logs(
        db: AsyncSession,
        *,
        format: str = "json",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> str:
        """Export audit logs in the requested format (json, csv, or syslog)."""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.asc())
        if date_from:
            stmt = stmt.where(AuditLog.timestamp >= date_from)
        if date_to:
            stmt = stmt.where(AuditLog.timestamp <= date_to)

        result = await db.execute(stmt)
        entries = result.scalars().all()

        if format == "json":
            rows = []
            for e in entries:
                rows.append(
                    {
                        "id": e.id,
                        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                        "user_id": str(e.user_id) if e.user_id else None,
                        "action": e.action,
                        "resource_type": e.resource_type,
                        "resource_id": e.resource_id,
                        "ip_address": e.ip_address,
                        "classification_level": e.classification_level,
                        "request_summary": e.request_summary,
                        "response_summary": e.response_summary,
                    }
                )
            return json.dumps(rows, indent=2, default=str)

        if format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(
                [
                    "id",
                    "timestamp",
                    "user_id",
                    "action",
                    "resource_type",
                    "resource_id",
                    "ip_address",
                    "classification_level",
                ]
            )
            for e in entries:
                writer.writerow(
                    [
                        e.id,
                        e.timestamp.isoformat() if e.timestamp else "",
                        str(e.user_id) if e.user_id else "",
                        e.action,
                        e.resource_type,
                        e.resource_id or "",
                        e.ip_address or "",
                        e.classification_level,
                    ]
                )
            return buf.getvalue()

        # syslog (RFC 5424-ish)
        lines: list[str] = []
        for e in entries:
            ts = e.timestamp.isoformat() if e.timestamp else "-"
            user = str(e.user_id) if e.user_id else "-"
            lines.append(
                f"<134>1 {ts} sovereign-ai gateway - - - "
                f"[audit user=\"{user}\" action=\"{e.action}\" "
                f"resource=\"{e.resource_type}/{e.resource_id or '-'}\" "
                f"classification=\"{e.classification_level}\" "
                f"ip=\"{e.ip_address or '-'}\"]"
            )
        return "\n".join(lines)

    # -- Stats -------------------------------------------------------------
    @staticmethod
    async def get_stats(
        db: AsyncSession,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Return aggregate audit statistics."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        base = select(func.count(AuditLog.id))
        if date_from:
            base = base.where(AuditLog.timestamp >= date_from)
        if date_to:
            base = base.where(AuditLog.timestamp <= date_to)

        total = (await db.execute(base)).scalar() or 0
        events_today = (
            await db.execute(base.where(AuditLog.timestamp >= today_start))
        ).scalar() or 0
        events_week = (
            await db.execute(base.where(AuditLog.timestamp >= week_start))
        ).scalar() or 0

        # Top actions
        top_actions_q = (
            select(AuditLog.action, func.count(AuditLog.id).label("count"))
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
            .limit(10)
        )
        top_actions = [
            {"action": r[0], "count": r[1]} for r in (await db.execute(top_actions_q)).all()
        ]

        # Top users
        top_users_q = (
            select(AuditLog.user_id, func.count(AuditLog.id).label("count"))
            .where(AuditLog.user_id.isnot(None))
            .group_by(AuditLog.user_id)
            .order_by(func.count(AuditLog.id).desc())
            .limit(10)
        )
        top_users = [
            {"user_id": str(r[0]), "count": r[1]} for r in (await db.execute(top_users_q)).all()
        ]

        # Events by day (last 30 days)
        thirty_days_ago = now - timedelta(days=30)
        by_day_q = (
            select(
                func.date_trunc("day", AuditLog.timestamp).label("day"),
                func.count(AuditLog.id).label("count"),
            )
            .where(AuditLog.timestamp >= thirty_days_ago)
            .group_by("day")
            .order_by("day")
        )
        events_by_day = [
            {"date": r[0].isoformat() if r[0] else None, "count": r[1]}
            for r in (await db.execute(by_day_q)).all()
        ]

        # By classification
        by_class_q = (
            select(AuditLog.classification_level, func.count(AuditLog.id).label("count"))
            .group_by(AuditLog.classification_level)
            .order_by(func.count(AuditLog.id).desc())
        )
        events_by_class = [
            {"classification": r[0], "count": r[1]}
            for r in (await db.execute(by_class_q)).all()
        ]

        return {
            "total_events": total,
            "events_today": events_today,
            "events_this_week": events_week,
            "top_actions": top_actions,
            "top_users": top_users,
            "events_by_day": events_by_day,
            "events_by_classification": events_by_class,
        }

    # -- Retention ---------------------------------------------------------
    @staticmethod
    async def cleanup_old_logs(days: int) -> int:
        """Delete audit logs older than *days*. Returns count of deleted rows."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        try:
            async with async_session() as db:
                result = await db.execute(
                    delete(AuditLog).where(AuditLog.timestamp < cutoff)
                )
                await db.commit()
                return result.rowcount  # type: ignore[return-value]
        except Exception:
            logger.exception("Failed to clean up audit logs older than %d days", days)
            return 0

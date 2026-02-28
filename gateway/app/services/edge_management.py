"""Edge Device management service — Phase 8.

Handles registration, listing, status tracking, and sync coordination for
edge agents that operate in disconnected environments.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password, verify_password
from app.models.edge import EdgeDevice, EdgeSyncLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Device registration
# ---------------------------------------------------------------------------


async def register_device(
    db: AsyncSession,
    name: str,
    agent_id: str | None = None,
    classification_level: str = "UNCLASSIFIED",
    metadata: dict | None = None,
) -> tuple[EdgeDevice, str]:
    """Register a new edge device and return (device, plaintext_api_key)."""
    if not agent_id:
        agent_id = f"edge-{uuid.uuid4().hex[:12]}"

    # Generate a secure API key
    api_key = f"sov-edge-{secrets.token_urlsafe(32)}"
    api_key_hash = hash_password(api_key)

    device = EdgeDevice(
        name=name,
        agent_id=agent_id,
        api_key_hash=api_key_hash,
        status="active",
        classification_level=classification_level,
        metadata_=metadata,
        sync_state={},
        config_version="1",
    )

    db.add(device)
    await db.flush()
    await db.refresh(device)

    logger.info("Registered edge device %s (agent_id=%s)", device.id, agent_id)
    return device, api_key


# ---------------------------------------------------------------------------
# Device CRUD
# ---------------------------------------------------------------------------


async def list_devices(
    db: AsyncSession,
    status_filter: str | None = None,
) -> list[EdgeDevice]:
    """List edge devices, optionally filtered by status."""
    stmt = select(EdgeDevice).order_by(EdgeDevice.created_at.desc())
    if status_filter:
        stmt = stmt.where(EdgeDevice.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_device(db: AsyncSession, device_id: uuid.UUID) -> EdgeDevice | None:
    """Get a single edge device by primary key."""
    return await db.get(EdgeDevice, device_id)


async def get_device_by_agent_id(db: AsyncSession, agent_id: str) -> EdgeDevice | None:
    """Get a single edge device by its agent_id."""
    stmt = select(EdgeDevice).where(EdgeDevice.agent_id == agent_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_device(
    db: AsyncSession,
    device_id: uuid.UUID,
    *,
    name: str | None = None,
    status: str | None = None,
    classification_level: str | None = None,
    config_version: str | None = None,
    metadata: dict | None = None,
) -> EdgeDevice | None:
    """Update an edge device's mutable fields."""
    device = await db.get(EdgeDevice, device_id)
    if device is None:
        return None

    if name is not None:
        device.name = name
    if status is not None:
        device.status = status
    if classification_level is not None:
        device.classification_level = classification_level
    if config_version is not None:
        device.config_version = config_version
    if metadata is not None:
        device.metadata_ = metadata

    await db.flush()
    await db.refresh(device)
    return device


async def deactivate_device(db: AsyncSession, device_id: uuid.UUID) -> EdgeDevice | None:
    """Revoke an edge device (set status to 'revoked')."""
    return await update_device(db, device_id, status="revoked")


# ---------------------------------------------------------------------------
# Device authentication
# ---------------------------------------------------------------------------


async def authenticate_device(
    db: AsyncSession,
    agent_id: str,
    api_key: str,
) -> EdgeDevice | None:
    """Validate an edge device's API key. Returns the device or None."""
    device = await get_device_by_agent_id(db, agent_id)
    if device is None:
        return None
    if device.status != "active":
        return None
    if not verify_password(api_key, device.api_key_hash):
        return None

    # Touch last_seen
    device.last_seen = datetime.now(timezone.utc)
    await db.flush()
    return device


# ---------------------------------------------------------------------------
# Sync bookkeeping
# ---------------------------------------------------------------------------


async def record_sync(
    db: AsyncSession,
    device_id: uuid.UUID,
    sync_type: str,
    direction: str,
    items_count: int,
    status: str = "success",
    error: str | None = None,
) -> EdgeSyncLog:
    """Record a sync event and update the device's sync_state."""
    now = datetime.now(timezone.utc)

    log = EdgeSyncLog(
        device_id=device_id,
        sync_type=sync_type,
        direction=direction,
        items_count=items_count,
        status=status,
        error=error,
        started_at=now,
        completed_at=now,
    )
    db.add(log)

    # Update device sync_state
    device = await db.get(EdgeDevice, device_id)
    if device:
        sync_state = device.sync_state or {}
        sync_state[f"{sync_type}_{direction}"] = {
            "last_sync": now.isoformat(),
            "items": items_count,
            "status": status,
        }
        device.sync_state = sync_state
        device.last_seen = now

    await db.flush()
    return log


async def get_device_sync_logs(
    db: AsyncSession,
    device_id: uuid.UUID,
    limit: int = 50,
) -> list[EdgeSyncLog]:
    """Get recent sync logs for a device."""
    stmt = (
        select(EdgeSyncLog)
        .where(EdgeSyncLog.device_id == device_id)
        .order_by(EdgeSyncLog.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Health monitoring
# ---------------------------------------------------------------------------


async def get_device_health_summary(db: AsyncSession) -> list[dict]:
    """Return a summary of all devices with their health status."""
    devices = await list_devices(db)
    now = datetime.now(timezone.utc)
    summaries = []

    for device in devices:
        health = "unknown"
        if device.status == "revoked":
            health = "revoked"
        elif device.last_seen:
            last = device.last_seen
            if hasattr(last, "tzinfo") and last.tzinfo is None:
                from datetime import timezone as tz

                last = last.replace(tzinfo=tz.utc)
            delta = (now - last).total_seconds()
            if delta < 600:  # 10 minutes
                health = "online"
            elif delta < 3600:  # 1 hour
                health = "stale"
            else:
                health = "offline"
        else:
            health = "never_seen"

        summaries.append(
            {
                "device_id": str(device.id),
                "name": device.name,
                "agent_id": device.agent_id,
                "status": device.status,
                "health": health,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                "classification_level": device.classification_level,
            }
        )

    return summaries

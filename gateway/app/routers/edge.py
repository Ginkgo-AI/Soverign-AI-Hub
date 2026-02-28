"""Edge Device management router — Phase 8.

Endpoints for registering, managing, and syncing with edge agents deployed
in disconnected environments.
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.edge import (
    EdgeConfigPush,
    EdgeDeviceCreate,
    EdgeDeviceListOut,
    EdgeDeviceOut,
    EdgeDeviceRegisterOut,
    EdgeDeviceUpdate,
    EdgeModelInfo,
    SyncConversationPayload,
    SyncKnowledgePayload,
    SyncResponse,
)
from app.services import edge_management as edge_svc

logger = logging.getLogger(__name__)

router = APIRouter()

MODELS_DIR = "/models"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_device_from_header(
    db: AsyncSession,
    x_edge_agent_id: str = Header(...),
    authorization: str = Header(""),
) -> "EdgeDevice":  # noqa: F821
    """Authenticate an edge device from request headers."""
    api_key = authorization.removeprefix("Bearer ").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing edge device API key",
        )
    device = await edge_svc.authenticate_device(db, x_edge_agent_id, api_key)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid edge device credentials",
        )
    return device


# ---------------------------------------------------------------------------
# Device management (admin endpoints — require user JWT)
# ---------------------------------------------------------------------------


@router.post(
    "/edge/devices",
    response_model=EdgeDeviceRegisterOut,
    status_code=status.HTTP_201_CREATED,
)
async def register_device(
    body: EdgeDeviceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Register a new edge device. Returns the device with a one-time API key."""
    device, api_key = await edge_svc.register_device(
        db,
        name=body.name,
        agent_id=body.agent_id,
        classification_level=body.classification_level,
        metadata=body.metadata,
    )

    out = EdgeDeviceRegisterOut.model_validate(device)
    out.api_key = api_key
    return out


@router.get("/edge/devices", response_model=EdgeDeviceListOut)
async def list_devices(
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all registered edge devices."""
    devices = await edge_svc.list_devices(db, status_filter=status_filter)
    return EdgeDeviceListOut(
        devices=[EdgeDeviceOut.model_validate(d) for d in devices],
        total=len(devices),
    )


@router.get("/edge/devices/{device_id}", response_model=EdgeDeviceOut)
async def get_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get edge device details and sync state."""
    device = await edge_svc.get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Edge device not found")
    return EdgeDeviceOut.model_validate(device)


@router.put("/edge/devices/{device_id}", response_model=EdgeDeviceOut)
async def update_device(
    device_id: uuid.UUID,
    body: EdgeDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update edge device configuration."""
    device = await edge_svc.update_device(
        db,
        device_id,
        name=body.name,
        status=body.status,
        classification_level=body.classification_level,
        config_version=body.config_version,
        metadata=body.metadata,
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Edge device not found")
    return EdgeDeviceOut.model_validate(device)


@router.delete(
    "/edge/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revoke and deactivate an edge device."""
    device = await edge_svc.deactivate_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Edge device not found")


# ---------------------------------------------------------------------------
# Sync endpoints (authenticated by edge device API key)
# ---------------------------------------------------------------------------


@router.post("/edge/sync/conversations", response_model=SyncResponse)
async def receive_conversations(
    body: SyncConversationPayload,
    db: AsyncSession = Depends(get_db),
    x_edge_agent_id: str = Header(...),
    authorization: str = Header(""),
):
    """Receive a conversation uploaded from an edge device."""
    device = await _get_device_from_header(db, x_edge_agent_id, authorization)

    # Record the sync event
    await edge_svc.record_sync(
        db,
        device_id=device.id,
        sync_type="conversations",
        direction="push",
        items_count=len(body.messages),
    )

    logger.info(
        "Received conversation %s from edge device %s (%d messages)",
        body.conversation.id,
        device.agent_id,
        len(body.messages),
    )

    return SyncResponse(
        status="ok",
        items_received=len(body.messages),
        message=f"Conversation {body.conversation.id} received",
    )


@router.get("/edge/sync/knowledge")
async def serve_knowledge_deltas(
    agent_id: str = Query(...),
    since: str = Query(""),
    db: AsyncSession = Depends(get_db),
    x_edge_agent_id: str = Header(...),
    authorization: str = Header(""),
):
    """Serve knowledge base deltas to an edge device since the given timestamp."""
    device = await _get_device_from_header(db, x_edge_agent_id, authorization)

    # Record the sync
    await edge_svc.record_sync(
        db,
        device_id=device.id,
        sync_type="knowledge",
        direction="pull",
        items_count=0,
    )

    # In a full implementation, this would query the knowledge base for chunks
    # created/updated after the 'since' timestamp. For now, return empty.
    return {"chunks": [], "since": since}


@router.get("/edge/sync/config")
async def serve_config(
    agent_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    x_edge_agent_id: str = Header(...),
    authorization: str = Header(""),
):
    """Serve the current config/policy for an edge device."""
    device = await _get_device_from_header(db, x_edge_agent_id, authorization)

    await edge_svc.record_sync(
        db,
        device_id=device.id,
        sync_type="config",
        direction="pull",
        items_count=0,
    )

    return EdgeConfigPush(
        config_version=device.config_version,
        classification_level=device.classification_level,
        allowed_models=None,
        policy=None,
    )


@router.get("/edge/sync/models")
async def list_available_models(
    agent_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    x_edge_agent_id: str = Header(...),
    authorization: str = Header(""),
):
    """List models available for download by edge devices."""
    device = await _get_device_from_header(db, x_edge_agent_id, authorization)

    models = []
    llm_dir = os.path.join(MODELS_DIR, "llm")
    if os.path.isdir(llm_dir):
        for entry in os.scandir(llm_dir):
            if entry.name.endswith(".gguf") and entry.is_file():
                stat = entry.stat()
                quant = _detect_quantization(entry.name)
                models.append(
                    EdgeModelInfo(
                        name=entry.name.replace(".gguf", ""),
                        filename=entry.name,
                        size_bytes=stat.st_size,
                        quantization=quant,
                    )
                )

    return {"models": [m.model_dump() for m in models]}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_QUANT_MARKERS = [
    "Q2_K", "Q3_K_S", "Q3_K_M", "Q3_K_L",
    "Q4_0", "Q4_K_S", "Q4_K_M",
    "Q5_0", "Q5_K_S", "Q5_K_M",
    "Q6_K", "Q8_0", "F16", "F32",
]


def _detect_quantization(filename: str) -> str | None:
    upper = filename.upper()
    for q in _QUANT_MARKERS:
        if q in upper:
            return q
    return None

"""Plugin tool CRUD and management endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.plugin import PluginTool
from app.schemas.plugin import PluginCreate, PluginListOut, PluginOut, PluginUpdate
from app.services.plugin_manager import compile_handler, load_plugin, unload_plugin

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/plugins", response_model=PluginListOut)
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(PluginTool).order_by(PluginTool.created_at))
    plugins = result.scalars().all()
    return PluginListOut(
        plugins=[PluginOut.model_validate(p) for p in plugins],
        total=len(plugins),
    )


@router.post("/plugins", response_model=PluginOut, status_code=status.HTTP_201_CREATED)
async def create_plugin(
    body: PluginCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Validate handler compiles
    try:
        compile_handler(body.name, body.handler_module)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    plugin = PluginTool(
        name=body.name,
        description=body.description,
        version=body.version,
        category=body.category,
        parameters_schema=body.parameters_schema,
        handler_module=body.handler_module,
        requires_approval=body.requires_approval,
        manifest=body.manifest,
        installed_by=user.id,
    )
    db.add(plugin)
    await db.flush()
    await db.refresh(plugin)
    return PluginOut.model_validate(plugin)


@router.get("/plugins/{plugin_id}", response_model=PluginOut)
async def get_plugin(
    plugin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(PluginTool).where(PluginTool.id == plugin_id))
    plugin = result.scalar_one_or_none()
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return PluginOut.model_validate(plugin)


@router.put("/plugins/{plugin_id}", response_model=PluginOut)
async def update_plugin(
    plugin_id: uuid.UUID,
    body: PluginUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(PluginTool).where(PluginTool.id == plugin_id))
    plugin = result.scalar_one_or_none()
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    update_data = body.model_dump(exclude_unset=True)
    if "handler_module" in update_data:
        try:
            compile_handler(plugin.name, update_data["handler_module"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    for field, value in update_data.items():
        setattr(plugin, field, value)
    await db.flush()
    await db.refresh(plugin)
    return PluginOut.model_validate(plugin)


@router.delete("/plugins/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin(
    plugin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(PluginTool).where(PluginTool.id == plugin_id))
    plugin = result.scalar_one_or_none()
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    if plugin.enabled:
        unload_plugin(plugin.name)
    await db.delete(plugin)
    await db.flush()


@router.post("/plugins/{plugin_id}/enable", response_model=PluginOut)
async def enable_plugin(
    plugin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(PluginTool).where(PluginTool.id == plugin_id))
    plugin = result.scalar_one_or_none()
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    try:
        load_plugin(plugin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    plugin.enabled = True
    await db.flush()
    await db.refresh(plugin)
    return PluginOut.model_validate(plugin)


@router.post("/plugins/{plugin_id}/disable", response_model=PluginOut)
async def disable_plugin(
    plugin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(PluginTool).where(PluginTool.id == plugin_id))
    plugin = result.scalar_one_or_none()
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    unload_plugin(plugin.name)
    plugin.enabled = False
    await db.flush()
    await db.refresh(plugin)
    return PluginOut.model_validate(plugin)

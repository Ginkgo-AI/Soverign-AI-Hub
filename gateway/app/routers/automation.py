"""Automation endpoints — schedules, watchers, and logs."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.automation import AutomationLog, Schedule, Watcher
from app.schemas.automation import (
    AutomationLogListOut,
    AutomationLogOut,
    ScheduleCreate,
    ScheduleListOut,
    ScheduleOut,
    ScheduleUpdate,
    WatcherCreate,
    WatcherListOut,
    WatcherOut,
    WatcherUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# -- Schedules ----------------------------------------------------------------

@router.get("/automation/schedules", response_model=ScheduleListOut)
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Schedule).order_by(Schedule.created_at))
    schedules = result.scalars().all()
    return ScheduleListOut(
        schedules=[ScheduleOut.model_validate(s) for s in schedules],
        total=len(schedules),
    )


@router.post("/automation/schedules", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    schedule = Schedule(
        name=body.name,
        cron_expression=body.cron_expression,
        agent_id=body.agent_id,
        prompt=body.prompt,
        enabled=body.enabled,
        created_by=user.id,
    )
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)

    # Refresh the scheduler
    from app.services.scheduler_service import refresh_schedules
    try:
        await refresh_schedules(db)
    except Exception:
        logger.exception("Failed to refresh scheduler after create")

    return ScheduleOut.model_validate(schedule)


@router.put("/automation/schedules/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)
    await db.flush()
    await db.refresh(schedule)

    from app.services.scheduler_service import refresh_schedules
    try:
        await refresh_schedules(db)
    except Exception:
        logger.exception("Failed to refresh scheduler after update")

    return ScheduleOut.model_validate(schedule)


@router.delete("/automation/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(schedule)
    await db.flush()

    from app.services.scheduler_service import refresh_schedules
    try:
        await refresh_schedules(db)
    except Exception:
        logger.exception("Failed to refresh scheduler after delete")


@router.post("/automation/schedules/{schedule_id}/trigger")
async def trigger_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    from app.services.scheduler_service import _execute_scheduled_job
    await _execute_scheduled_job(str(schedule_id))

    return {"status": "triggered", "schedule_id": str(schedule_id)}


# -- Watchers -----------------------------------------------------------------

@router.get("/automation/watchers", response_model=WatcherListOut)
async def list_watchers(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Watcher).order_by(Watcher.created_at))
    watchers = result.scalars().all()
    return WatcherListOut(
        watchers=[WatcherOut.model_validate(w) for w in watchers],
        total=len(watchers),
    )


@router.post("/automation/watchers", response_model=WatcherOut, status_code=status.HTTP_201_CREATED)
async def create_watcher(
    body: WatcherCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    watcher = Watcher(
        name=body.name,
        watch_path=body.watch_path,
        file_pattern=body.file_pattern,
        action_type=body.action_type,
        collection_id=body.collection_id,
        agent_id=body.agent_id,
        prompt_template=body.prompt_template,
        enabled=body.enabled,
        created_by=user.id,
    )
    db.add(watcher)
    await db.flush()
    await db.refresh(watcher)

    from app.services.watcher_service import refresh_watchers
    try:
        await refresh_watchers(db)
    except Exception:
        logger.exception("Failed to refresh watchers after create")

    return WatcherOut.model_validate(watcher)


@router.put("/automation/watchers/{watcher_id}", response_model=WatcherOut)
async def update_watcher(
    watcher_id: uuid.UUID,
    body: WatcherUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Watcher).where(Watcher.id == watcher_id))
    watcher = result.scalar_one_or_none()
    if watcher is None:
        raise HTTPException(status_code=404, detail="Watcher not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(watcher, field, value)
    await db.flush()
    await db.refresh(watcher)

    from app.services.watcher_service import refresh_watchers
    try:
        await refresh_watchers(db)
    except Exception:
        logger.exception("Failed to refresh watchers after update")

    return WatcherOut.model_validate(watcher)


@router.delete("/automation/watchers/{watcher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watcher(
    watcher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Watcher).where(Watcher.id == watcher_id))
    watcher = result.scalar_one_or_none()
    if watcher is None:
        raise HTTPException(status_code=404, detail="Watcher not found")
    await db.delete(watcher)
    await db.flush()

    from app.services.watcher_service import refresh_watchers
    try:
        await refresh_watchers(db)
    except Exception:
        logger.exception("Failed to refresh watchers after delete")


# -- Logs ---------------------------------------------------------------------

@router.get("/automation/logs", response_model=AutomationLogListOut)
async def list_automation_logs(
    trigger_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(AutomationLog).order_by(AutomationLog.created_at.desc()).limit(limit)
    if trigger_type:
        query = query.where(AutomationLog.trigger_type == trigger_type)

    result = await db.execute(query)
    logs = result.scalars().all()
    return AutomationLogListOut(
        logs=[AutomationLogOut.model_validate(log) for log in logs],
        total=len(logs),
    )

"""Scheduler service — APScheduler-based cron job execution."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.agent import AgentDefinition, AgentExecution
from app.models.automation import AutomationLog, Schedule

logger = logging.getLogger(__name__)

# APScheduler instance — lazily initialized
_scheduler = None


def _get_scheduler():
    """Lazily create the APScheduler instance."""
    global _scheduler
    if _scheduler is None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            _scheduler = AsyncIOScheduler()
        except ImportError:
            logger.warning("APScheduler not installed — scheduler disabled")
            return None
    return _scheduler


async def _execute_scheduled_job(schedule_id: str) -> None:
    """Triggered by APScheduler — runs the agent for a schedule."""
    async with async_session() as db:
        try:
            result = await db.execute(
                select(Schedule).where(Schedule.id == uuid.UUID(schedule_id))
            )
            schedule = result.scalar_one_or_none()
            if schedule is None or not schedule.enabled:
                return

            # Load agent
            agent_result = await db.execute(
                select(AgentDefinition).where(AgentDefinition.id == schedule.agent_id)
            )
            agent = agent_result.scalar_one_or_none()
            if agent is None:
                logger.error("Schedule %s references missing agent %s", schedule_id, schedule.agent_id)
                return

            # Create execution
            execution = AgentExecution(
                agent_id=agent.id,
                user_id=schedule.created_by,
                status="running",
                input_prompt=schedule.prompt,
            )
            db.add(execution)
            await db.flush()

            # Run agent
            from app.services.agent_executor import run_agent
            agent_result_obj = await run_agent(
                agent=agent,
                execution=execution,
                prompt=schedule.prompt,
                db=db,
                max_iterations=10,
                timeout_seconds=120.0,
            )

            # Update schedule status
            schedule.last_run_at = datetime.now(timezone.utc)
            schedule.last_status = agent_result_obj.status

            # Log automation run
            log = AutomationLog(
                trigger_type="schedule",
                trigger_id=schedule.id,
                status=agent_result_obj.status,
                execution_id=execution.id,
                details={"prompt": schedule.prompt[:200]},
            )
            db.add(log)
            await db.commit()

            logger.info("Schedule '%s' executed: status=%s", schedule.name, agent_result_obj.status)

        except Exception:
            logger.exception("Scheduled job %s failed", schedule_id)
            await db.rollback()


def _parse_cron(cron_expr: str) -> dict[str, str]:
    """Parse a 5-field cron expression into APScheduler kwargs."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


async def start_scheduler(db: AsyncSession) -> None:
    """Load enabled schedules and start the APScheduler."""
    scheduler = _get_scheduler()
    if scheduler is None:
        return

    result = await db.execute(
        select(Schedule).where(Schedule.enabled == True)  # noqa: E712
    )
    schedules = result.scalars().all()

    for sched in schedules:
        try:
            cron_kwargs = _parse_cron(sched.cron_expression)
            scheduler.add_job(
                _execute_scheduled_job,
                "cron",
                args=[str(sched.id)],
                id=f"schedule_{sched.id}",
                replace_existing=True,
                **cron_kwargs,
            )
        except Exception:
            logger.exception("Failed to load schedule: %s", sched.name)

    if not scheduler.running:
        scheduler.start()
    logger.info("Scheduler started with %d schedules", len(schedules))


async def stop_scheduler() -> None:
    """Gracefully stop the scheduler."""
    scheduler = _get_scheduler()
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def refresh_schedules(db: AsyncSession) -> None:
    """Reload all schedules (call after CRUD operations)."""
    scheduler = _get_scheduler()
    if scheduler is None:
        return

    # Remove all existing schedule jobs
    for job in scheduler.get_jobs():
        if job.id.startswith("schedule_"):
            scheduler.remove_job(job.id)

    # Re-add enabled schedules
    result = await db.execute(
        select(Schedule).where(Schedule.enabled == True)  # noqa: E712
    )
    schedules = result.scalars().all()

    for sched in schedules:
        try:
            cron_kwargs = _parse_cron(sched.cron_expression)
            scheduler.add_job(
                _execute_scheduled_job,
                "cron",
                args=[str(sched.id)],
                id=f"schedule_{sched.id}",
                replace_existing=True,
                **cron_kwargs,
            )
        except Exception:
            logger.exception("Failed to reload schedule: %s", sched.name)

    logger.info("Refreshed %d schedules", len(schedules))

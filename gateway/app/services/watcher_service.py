"""Watcher service — filesystem monitoring for auto-ingest and agent triggers."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.automation import AutomationLog, Watcher

logger = logging.getLogger(__name__)

# Active watcher tasks
_watcher_tasks: dict[str, asyncio.Task] = {}


async def _poll_directory(watcher_id: str, watch_path: str, file_pattern: str, interval: float = 5.0) -> None:
    """Poll a directory for changes and trigger actions."""
    seen_files: set[str] = set()
    path = Path(watch_path)

    # Initial scan
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file() and fnmatch.fnmatch(f.name, file_pattern):
                seen_files.add(str(f))

    while True:
        try:
            await asyncio.sleep(interval)

            if not path.exists():
                continue

            current_files: set[str] = set()
            for f in path.rglob("*"):
                if f.is_file() and fnmatch.fnmatch(f.name, file_pattern):
                    current_files.add(str(f))

            new_files = current_files - seen_files
            if new_files:
                for file_path in new_files:
                    await _handle_new_file(watcher_id, file_path)
                seen_files = current_files

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Watcher %s polling error", watcher_id)
            await asyncio.sleep(30)


async def _handle_new_file(watcher_id: str, file_path: str) -> None:
    """Handle a newly detected file."""
    async with async_session() as db:
        try:
            result = await db.execute(
                select(Watcher).where(Watcher.id == uuid.UUID(watcher_id))
            )
            watcher = result.scalar_one_or_none()
            if watcher is None or not watcher.enabled:
                return

            logger.info("Watcher '%s' detected new file: %s", watcher.name, file_path)

            if watcher.action_type == "ingest" and watcher.collection_id:
                # Push to Redis document_jobs queue for processing
                try:
                    import redis.asyncio as aioredis
                    from app.config import settings
                    r = aioredis.Redis(host=settings.redis_host, port=settings.redis_port)
                    await r.xadd("document_jobs", {
                        "file_path": file_path,
                        "collection_id": str(watcher.collection_id),
                        "source": f"watcher:{watcher.name}",
                    })
                    await r.aclose()
                    status = "success"
                except Exception:
                    logger.exception("Failed to queue ingest job")
                    status = "failed"

                log = AutomationLog(
                    trigger_type="watcher",
                    trigger_id=watcher.id,
                    status=status,
                    details={"file_path": file_path, "action": "ingest"},
                )
                db.add(log)

            elif watcher.action_type == "agent" and watcher.agent_id:
                # Trigger agent execution
                from app.models.agent import AgentDefinition, AgentExecution
                agent_result = await db.execute(
                    select(AgentDefinition).where(AgentDefinition.id == watcher.agent_id)
                )
                agent = agent_result.scalar_one_or_none()
                if agent is None:
                    return

                prompt = (watcher.prompt_template or "Process this file: {file_path}").format(
                    file_path=file_path
                )

                execution = AgentExecution(
                    agent_id=agent.id,
                    user_id=watcher.created_by,
                    status="running",
                    input_prompt=prompt,
                )
                db.add(execution)
                await db.flush()

                from app.services.agent_executor import run_agent
                agent_result_obj = await run_agent(
                    agent=agent,
                    execution=execution,
                    prompt=prompt,
                    db=db,
                    max_iterations=10,
                    timeout_seconds=120.0,
                )

                log = AutomationLog(
                    trigger_type="watcher",
                    trigger_id=watcher.id,
                    status=agent_result_obj.status,
                    execution_id=execution.id,
                    details={"file_path": file_path, "action": "agent"},
                )
                db.add(log)

            await db.commit()

        except Exception:
            logger.exception("Watcher %s file handling failed for %s", watcher_id, file_path)
            await db.rollback()


async def start_watchers(db: AsyncSession) -> None:
    """Start polling tasks for all enabled watchers."""
    result = await db.execute(
        select(Watcher).where(Watcher.enabled == True)  # noqa: E712
    )
    watchers = result.scalars().all()

    for watcher in watchers:
        task_key = str(watcher.id)
        if task_key not in _watcher_tasks:
            task = asyncio.create_task(
                _poll_directory(task_key, watcher.watch_path, watcher.file_pattern)
            )
            _watcher_tasks[task_key] = task

    logger.info("Started %d file watchers", len(watchers))


async def stop_watchers() -> None:
    """Cancel all watcher polling tasks."""
    for task_id, task in _watcher_tasks.items():
        task.cancel()
    _watcher_tasks.clear()
    logger.info("All file watchers stopped")


async def refresh_watchers(db: AsyncSession) -> None:
    """Reload watchers after CRUD operations."""
    await stop_watchers()
    await start_watchers(db)

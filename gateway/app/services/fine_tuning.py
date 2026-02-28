"""Fine-Tuning Service — Phase 7.

Orchestrates LoRA/QLoRA training jobs via Redis Streams, tracks progress,
and manages adapters.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.training import TrainingJob

logger = logging.getLogger(__name__)

REDIS_STREAM = "training_jobs"
ADAPTERS_DIR = "/models/adapters"

# Training presets
PRESETS = {
    "quick": {
        "epochs": 1,
        "learning_rate": 3e-4,
        "batch_size": 8,
        "lora_rank": 8,
        "lora_alpha": 16,
        "warmup_steps": 5,
        "gradient_accumulation_steps": 2,
    },
    "standard": {
        "epochs": 3,
        "learning_rate": 2e-4,
        "batch_size": 4,
        "lora_rank": 16,
        "lora_alpha": 32,
        "warmup_steps": 10,
        "gradient_accumulation_steps": 4,
    },
    "thorough": {
        "epochs": 5,
        "learning_rate": 1e-4,
        "batch_size": 2,
        "lora_rank": 32,
        "lora_alpha": 64,
        "warmup_steps": 20,
        "gradient_accumulation_steps": 8,
    },
}


def _get_redis() -> aioredis.Redis:
    return aioredis.Redis(
        host=settings.redis_host, port=settings.redis_port, decode_responses=True
    )


def _apply_preset(config: dict) -> dict:
    """Apply a preset to the configuration if specified."""
    preset_name = config.pop("preset", None)
    if preset_name and preset_name in PRESETS:
        preset = PRESETS[preset_name].copy()
        # User overrides take priority; preset fills in defaults
        for key, value in preset.items():
            if key not in config or config[key] is None:
                config[key] = value
    return config


# ---------------------------------------------------------------------------
# Job management
# ---------------------------------------------------------------------------

async def start_training(
    db: AsyncSession,
    user_id: uuid.UUID,
    config: dict,
) -> TrainingJob:
    """Create a training job and dispatch it to the worker via Redis Streams."""
    config = _apply_preset(config)

    base_model = config.get("base_model", "")
    dataset_path = config.get("dataset_path", "")
    output_dir = config.get("output_dir", ADAPTERS_DIR)

    job = TrainingJob(
        user_id=user_id,
        base_model=base_model,
        dataset_path=dataset_path,
        config=config,
        status="pending",
        progress=0.0,
        output_path=os.path.join(output_dir, str(uuid.uuid4())),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Enqueue to Redis Streams
    payload = {
        "job_id": str(job.id),
        "base_model": base_model,
        "dataset_path": dataset_path,
        "output_path": job.output_path,
        "config": json.dumps(config),
    }

    try:
        r = _get_redis()
        await r.xadd(REDIS_STREAM, {"payload": json.dumps(payload)})
        await r.aclose()
        logger.info("Queued training job: %s", job.id)
    except Exception:
        logger.exception("Failed to queue training job %s", job.id)
        job.status = "failed"
        job.error_message = "Failed to queue job to Redis"
        await db.flush()

    return job


async def get_training_status(
    db: AsyncSession, job_id: uuid.UUID
) -> TrainingJob | None:
    """Get training job with current status."""
    result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return None

    # Also try to read live progress from Redis
    try:
        r = _get_redis()
        progress_data = await r.get(f"training_progress:{job_id}")
        await r.aclose()
        if progress_data:
            data = json.loads(progress_data)
            job.progress = data.get("progress", job.progress)
            if data.get("metrics"):
                job.metrics = data["metrics"]
    except Exception:
        pass

    return job


async def list_training_jobs(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    status_filter: str | None = None,
) -> list[TrainingJob]:
    """List training jobs with optional filtering."""
    stmt = select(TrainingJob).order_by(TrainingJob.created_at.desc())
    if user_id:
        stmt = stmt.where(TrainingJob.user_id == user_id)
    if status_filter:
        stmt = stmt.where(TrainingJob.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def cancel_training(
    db: AsyncSession, job_id: uuid.UUID
) -> TrainingJob | None:
    """Cancel a pending or running training job."""
    result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return None

    if job.status in ("completed", "failed", "cancelled"):
        return job

    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc).isoformat()

    # Signal cancellation via Redis
    try:
        r = _get_redis()
        await r.set(f"training_cancel:{job_id}", "1", ex=3600)
        await r.aclose()
    except Exception:
        logger.warning("Could not signal cancellation via Redis for job %s", job_id)

    await db.flush()
    await db.refresh(job)
    return job


async def get_training_metrics(
    db: AsyncSession, job_id: uuid.UUID
) -> dict:
    """Get detailed training metrics including loss curve data."""
    result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return {}

    metrics: dict = {
        "job_id": str(job_id),
        "loss_history": [],
        "eval_history": [],
        "final_metrics": None,
    }

    # Try reading from Redis for live jobs
    try:
        r = _get_redis()
        loss_data = await r.lrange(f"training_loss:{job_id}", 0, -1)
        eval_data = await r.lrange(f"training_eval:{job_id}", 0, -1)
        await r.aclose()
        metrics["loss_history"] = [json.loads(d) for d in loss_data]
        metrics["eval_history"] = [json.loads(d) for d in eval_data]
    except Exception:
        pass

    # Also include metrics stored in the DB
    if job.metrics:
        metrics["final_metrics"] = job.metrics
        if "loss_history" in job.metrics and not metrics["loss_history"]:
            metrics["loss_history"] = job.metrics["loss_history"]
        if "eval_history" in job.metrics and not metrics["eval_history"]:
            metrics["eval_history"] = job.metrics["eval_history"]

    return metrics


# ---------------------------------------------------------------------------
# Adapter management
# ---------------------------------------------------------------------------

async def list_adapters() -> list[dict]:
    """List all saved adapters."""
    adapters: list[dict] = []
    base = Path(ADAPTERS_DIR)
    if not base.exists():
        return adapters

    for adapter_dir in sorted(base.iterdir()):
        if not adapter_dir.is_dir():
            continue
        config_path = adapter_dir / "adapter_config.json"
        info: dict = {
            "job_id": adapter_dir.name,
            "path": str(adapter_dir),
            "base_model": None,
            "created_at": None,
        }
        if config_path.exists():
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                info["base_model"] = cfg.get("base_model_name_or_path")
            except (json.JSONDecodeError, OSError):
                pass
        # Use directory mtime as creation time
        try:
            info["created_at"] = datetime.fromtimestamp(
                adapter_dir.stat().st_mtime, tz=timezone.utc
            ).isoformat()
        except OSError:
            pass
        adapters.append(info)

    return adapters


async def delete_adapter(job_id: str) -> bool:
    """Delete an adapter directory."""
    adapter_path = Path(ADAPTERS_DIR) / job_id
    if not adapter_path.exists():
        return False
    import shutil
    shutil.rmtree(adapter_path, ignore_errors=True)
    return True


async def merge_adapter(base_model_path: str, adapter_path: str, output_path: str) -> str:
    """Merge a LoRA adapter with a base model. Returns the merged output path.

    This is a placeholder that dispatches the merge to a worker. Actual merge
    requires loading the full model, which is done in the training worker.
    """
    r = _get_redis()
    payload = {
        "action": "merge_adapter",
        "base_model_path": base_model_path,
        "adapter_path": adapter_path,
        "output_path": output_path,
    }
    await r.xadd(REDIS_STREAM, {"payload": json.dumps(payload)})
    await r.aclose()
    return output_path

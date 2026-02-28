"""Training, Dataset, and Evaluation router — Phase 7.

Endpoints for fine-tuning jobs, dataset management, benchmarks, and A/B testing.
"""

from __future__ import annotations

import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.model_management import (
    ABTestCreate,
    ABTestOut,
    ABTestResult,
    ABTestVote,
    AdapterListOut,
    BenchmarkComparison,
    BenchmarkRequest,
    BenchmarkResult,
    BenchmarkResultListOut,
    CompareRequest,
    DatasetFromConversationsRequest,
    DatasetListOut,
    DatasetOut,
    DatasetPreview,
    DatasetStats,
    DatasetUpload,
    TrainingConfig,
    TrainingJobListOut,
    TrainingJobOut,
    TrainingMetricsOut,
)
from app.services import dataset as dataset_svc
from app.services import evaluation as evaluation_svc
from app.services import fine_tuning

logger = logging.getLogger(__name__)

router = APIRouter()

DATASETS_UPLOAD_DIR = "/models/datasets"


# =========================================================================
# Training jobs
# =========================================================================

@router.post(
    "/training/jobs",
    response_model=TrainingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_training_job(
    body: TrainingConfig,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a new fine-tuning training job."""
    config = body.model_dump()

    # If dataset_id provided, resolve to path
    if body.dataset_id:
        ds = await dataset_svc.get_dataset(db, body.dataset_id)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        config["dataset_path"] = ds.file_path

    if not config.get("dataset_path"):
        raise HTTPException(status_code=400, detail="dataset_path or dataset_id is required")

    job = await fine_tuning.start_training(db, user.id, config)
    return TrainingJobOut.model_validate(job)


@router.get("/training/jobs", response_model=TrainingJobListOut)
async def list_training_jobs(
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all training jobs."""
    jobs = await fine_tuning.list_training_jobs(db, user_id=user.id, status_filter=status_filter)
    return TrainingJobListOut(
        jobs=[TrainingJobOut.model_validate(j) for j in jobs],
        total=len(jobs),
    )


@router.get("/training/jobs/{job_id}", response_model=TrainingJobOut)
async def get_training_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get training job status and progress."""
    job = await fine_tuning.get_training_status(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    return TrainingJobOut.model_validate(job)


@router.post("/training/jobs/{job_id}/cancel", response_model=TrainingJobOut)
async def cancel_training_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel a pending or running training job."""
    job = await fine_tuning.cancel_training(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    return TrainingJobOut.model_validate(job)


@router.get("/training/jobs/{job_id}/metrics", response_model=TrainingMetricsOut)
async def get_training_metrics(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get training metrics (loss curve data)."""
    metrics = await fine_tuning.get_training_metrics(db, job_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Training job not found")
    return TrainingMetricsOut(
        job_id=job_id,
        loss_history=metrics.get("loss_history", []),
        eval_history=metrics.get("eval_history", []),
        final_metrics=metrics.get("final_metrics"),
    )


@router.get("/training/adapters", response_model=AdapterListOut)
async def list_adapters(user: User = Depends(get_current_user)):
    """List all saved LoRA adapters."""
    adapters = await fine_tuning.list_adapters()
    from app.schemas.model_management import AdapterInfo
    from datetime import datetime

    adapter_infos = []
    for a in adapters:
        created_at = None
        if a.get("created_at"):
            try:
                created_at = datetime.fromisoformat(a["created_at"])
            except (ValueError, TypeError):
                pass
        try:
            job_uuid = uuid.UUID(a["job_id"])
        except (ValueError, KeyError):
            continue
        adapter_infos.append(AdapterInfo(
            job_id=job_uuid,
            base_model=a.get("base_model") or "unknown",
            path=a.get("path", ""),
            created_at=created_at,
        ))

    return AdapterListOut(adapters=adapter_infos, total=len(adapter_infos))


@router.delete("/training/adapters/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_adapter(
    job_id: str,
    user: User = Depends(get_current_user),
):
    """Delete a LoRA adapter."""
    deleted = await fine_tuning.delete_adapter(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Adapter not found")


# =========================================================================
# Datasets
# =========================================================================

@router.post(
    "/training/datasets",
    response_model=DatasetOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    name: str = Query(...),
    format: str = Query("jsonl"),
    file: UploadFile = File(..., description="Dataset file (JSONL or CSV)"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a training dataset."""
    # Validate file extension
    filename = file.filename or "dataset"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".jsonl", ".csv", ".json"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: .jsonl, .csv, .json",
        )

    # Read and save file
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:  # 100 MB limit
        raise HTTPException(status_code=413, detail="File exceeds 100MB limit")

    os.makedirs(DATASETS_UPLOAD_DIR, exist_ok=True)
    ds_id = uuid.uuid4()
    file_path = os.path.join(DATASETS_UPLOAD_DIR, f"{ds_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Validate
    validation = await dataset_svc.validate_dataset(file_path)
    if not validation["valid"]:
        # Clean up
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid dataset", "errors": validation["errors"]},
        )

    # Get stats
    stats = await dataset_svc.get_dataset_stats(file_path)

    # Create DB record
    from app.models.training import TrainingDataset

    dataset = TrainingDataset(
        id=ds_id,
        user_id=user.id,
        name=name,
        format=format if format != "jsonl" else validation.get("schema", "jsonl"),
        file_path=file_path,
        sample_count=validation.get("sample_count", 0),
        token_stats=stats,
    )
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)

    return DatasetOut.model_validate(dataset)


@router.get("/training/datasets", response_model=DatasetListOut)
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all training datasets."""
    datasets = await dataset_svc.list_datasets(db, user_id=user.id)
    return DatasetListOut(
        datasets=[DatasetOut.model_validate(d) for d in datasets],
        total=len(datasets),
    )


@router.get("/training/datasets/{ds_id}", response_model=DatasetOut)
async def get_dataset(
    ds_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get dataset details and stats."""
    ds = await dataset_svc.get_dataset(db, ds_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetOut.model_validate(ds)


@router.get("/training/datasets/{ds_id}/stats", response_model=DatasetStats)
async def get_dataset_stats(
    ds_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed dataset statistics."""
    ds = await dataset_svc.get_dataset(db, ds_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    stats = await dataset_svc.get_dataset_stats(ds.file_path)
    validation = await dataset_svc.validate_dataset(ds.file_path)

    return DatasetStats(
        sample_count=stats.get("sample_count", 0),
        avg_token_length=stats.get("avg_token_length", 0),
        min_token_length=stats.get("min_token_length", 0),
        max_token_length=stats.get("max_token_length", 0),
        token_distribution=stats.get("token_distribution"),
        format_detected=validation.get("schema", "unknown"),
        schema_fields=validation.get("fields", []),
    )


@router.get("/training/datasets/{ds_id}/preview", response_model=DatasetPreview)
async def preview_dataset(
    ds_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Preview first N samples from a dataset."""
    ds = await dataset_svc.get_dataset(db, ds_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    samples = await dataset_svc.preview_dataset(ds.file_path, limit=limit)
    return DatasetPreview(samples=samples, total=ds.sample_count)


@router.post(
    "/training/datasets/from-conversations",
    response_model=DatasetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_from_conversations(
    body: DatasetFromConversationsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a training dataset from conversation history."""
    dataset = await dataset_svc.create_from_conversations(
        db=db,
        user_id=user.id,
        conversation_ids=body.conversation_ids,
        name=body.name,
        output_format=body.format,
    )
    return DatasetOut.model_validate(dataset)


@router.delete(
    "/training/datasets/{ds_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dataset(
    ds_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a dataset."""
    deleted = await dataset_svc.delete_dataset(db, ds_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")


# =========================================================================
# Evaluation / Benchmarks
# =========================================================================

@router.post("/evaluation/benchmark", response_model=BenchmarkResult)
async def run_benchmark(
    body: BenchmarkRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a benchmark on a model."""
    try:
        evaluation = await evaluation_svc.run_benchmark(
            db, body.model_name, body.benchmark
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BenchmarkResult.model_validate(evaluation)


@router.get("/evaluation/results", response_model=BenchmarkResultListOut)
async def list_evaluation_results(
    model_name: str | None = Query(None),
    benchmark: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List evaluation results."""
    results = await evaluation_svc.list_evaluation_results(
        db, model_name=model_name, benchmark=benchmark
    )
    return BenchmarkResultListOut(
        results=[BenchmarkResult.model_validate(r) for r in results],
        total=len(results),
    )


@router.post("/evaluation/compare", response_model=BenchmarkComparison)
async def compare_models(
    body: CompareRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compare two models on the same benchmark."""
    try:
        result = await evaluation_svc.compare_models(
            db, body.model_a, body.model_b, body.benchmark
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BenchmarkComparison(**result)


# =========================================================================
# A/B Testing
# =========================================================================

@router.post(
    "/evaluation/ab-test",
    response_model=ABTestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_ab_test(
    body: ABTestCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create an A/B test between two models."""
    test = await evaluation_svc.create_ab_test(
        db, user.id, body.model_a, body.model_b, body.traffic_split
    )
    return ABTestOut.model_validate(test)


@router.get("/evaluation/ab-test/{test_id}", response_model=ABTestResult)
async def get_ab_test_results(
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get A/B test results."""
    result = await evaluation_svc.get_ab_results(db, test_id)
    if not result:
        raise HTTPException(status_code=404, detail="A/B test not found")
    return ABTestResult(**result)


@router.post("/evaluation/ab-test/{test_id}/vote", response_model=ABTestOut)
async def vote_ab_test(
    test_id: uuid.UUID,
    body: ABTestVote,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record a preference vote for an A/B test."""
    test = await evaluation_svc.record_ab_vote(
        db, test_id, body.preferred_model, body.rating
    )
    if test is None:
        raise HTTPException(status_code=404, detail="A/B test not found or not active")
    return ABTestOut.model_validate(test)

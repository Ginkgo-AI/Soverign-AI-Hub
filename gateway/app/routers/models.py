"""Model Registry router — Phase 7.

Provides:
  - OpenAI-compatible /v1/models (via `v1_router`, mounted at /v1)
  - Full CRUD /api/models/* (via `router`, mounted at /api)
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.model_management import (
    ModelDownloadOut,
    ModelDownloadRequest,
    ModelListOut,
    ModelOut,
    ModelRegister,
    ModelScanRequest,
    ModelScanResult,
    ModelUpdate,
)
from app.services import model_registry
from app.services.llm import llm_backend

logger = logging.getLogger(__name__)

# OpenAI-compatible router (mounted at /v1)
v1_router = APIRouter()

# Application router (mounted at /api)
router = APIRouter()


# =========================================================================
# OpenAI-compatible endpoint  — /v1/models
# =========================================================================

@v1_router.get("/models")
async def list_models_openai():
    """List available models from all backends. OpenAI-compatible."""
    all_models: list[dict] = []

    for backend in ("vllm", "llama-cpp"):
        try:
            result = await llm_backend.list_models(backend)
            for model in result.get("data", []):
                model["_backend"] = backend
                all_models.append(model)
        except Exception:
            pass

    return {"object": "list", "data": all_models}


# =========================================================================
# Application model registry endpoints — /api/models/*
# =========================================================================

@router.get("/models", response_model=ModelListOut)
async def list_registered_models(
    backend: str | None = Query(None),
    model_status: str | None = Query(None, alias="status"),
    quantization: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all registered models with full metadata."""
    models = await model_registry.list_models(
        db, backend=backend, status=model_status, quantization=quantization,
    )
    return ModelListOut(
        models=[ModelOut.model_validate(m) for m in models],
        total=len(models),
    )


@router.get("/models/{model_id}", response_model=ModelOut)
async def get_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get model details."""
    model = await model_registry.get_model(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelOut.model_validate(model)


@router.post("/models", response_model=ModelOut, status_code=status.HTTP_201_CREATED)
async def register_model(
    body: ModelRegister,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Register a new model in the registry."""
    existing = await model_registry.get_model_by_name(db, body.name)
    if existing:
        raise HTTPException(status_code=409, detail="Model with this name already exists")

    model = await model_registry.register_model(
        db=db,
        name=body.name,
        backend=body.backend,
        file_path=body.file_path,
        version=body.version,
        quantization=body.quantization,
        parameters=body.parameters,
    )
    return ModelOut.model_validate(model)


@router.put("/models/{model_id}", response_model=ModelOut)
async def update_model(
    model_id: uuid.UUID,
    body: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update model metadata."""
    updates = body.model_dump(exclude_unset=True)
    model = await model_registry.update_model(db, model_id, updates)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelOut.model_validate(model)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: uuid.UUID,
    delete_files: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete model from registry and optionally from disk."""
    deleted = await model_registry.delete_model(db, model_id, delete_files=delete_files)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")


@router.post("/models/scan", response_model=ModelScanResult)
async def scan_model_directory(
    body: ModelScanRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Scan model directory and auto-register discovered models."""
    path = body.path if body else "/models"
    discovered = await model_registry.scan_model_directory(db, path)
    return ModelScanResult(
        discovered=len(discovered),
        registered=len(discovered),
        models=[ModelOut.model_validate(m) for m in discovered],
    )


@router.post("/models/download", response_model=ModelDownloadOut)
async def download_model(
    body: ModelDownloadRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download model from HuggingFace Hub (non-airgap) or import from local path."""
    from app.config import settings

    if settings.airgap_mode and not body.source.startswith("/"):
        raise HTTPException(
            status_code=400,
            detail="Cannot download from remote sources in air-gap mode. Use a local path.",
        )

    try:
        dest_path = await model_registry.download_model(
            source=body.source,
            destination=body.destination,
            filename=body.filename,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {e}")

    # Auto-register the downloaded model
    name = body.filename or body.source.split("/")[-1]
    backend = "llama-cpp" if name.endswith(".gguf") else "vllm"
    model = await model_registry.register_model(
        db=db,
        name=name.replace(".gguf", ""),
        backend=backend,
        file_path=dest_path,
    )

    return ModelDownloadOut(
        model_id=model.id,
        status="available",
        message=f"Model downloaded and registered: {dest_path}",
    )

"""Model management endpoints: discovery, load/unload, config, system resources."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.middleware.auth import get_optional_user
from app.services.model_manager import model_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model-management")


class LoadModelRequest(BaseModel):
    model: str
    backend: str = "llama-cpp"
    keep_alive: str = "5m"


class UnloadModelRequest(BaseModel):
    model: str
    backend: str = "llama-cpp"


class ModelConfigRequest(BaseModel):
    model: str | None = None
    backend: str | None = None
    context_length: int | None = None
    keep_alive: str | None = None


# In-memory config shared across all requests in this process. Resets on server restart.
_active_config: dict[str, Any] = {
    "model": "",
    "backend": "vllm",
    "context_length": 8192,
    "keep_alive": "5m",
}


@router.get("/available")
async def list_available_models(user=Depends(get_optional_user)):
    """List all models from both backends with metadata."""
    try:
        models = await model_manager.list_available_models()
    except Exception as e:
        logger.exception("Failed to list available models")
        raise HTTPException(status_code=502, detail=f"Failed to query model backends: {e}")
    return {"models": models, "count": len(models)}


@router.get("/loaded")
async def list_loaded_models(user=Depends(get_optional_user)):
    """List currently loaded models."""
    try:
        models = await model_manager.list_loaded_models()
    except Exception as e:
        logger.exception("Failed to list loaded models")
        raise HTTPException(status_code=502, detail=f"Failed to query model backends: {e}")
    return {"models": models, "count": len(models)}


@router.post("/load")
async def load_model(request: LoadModelRequest, user=Depends(get_optional_user)):
    """Load a model into memory (llama.cpp only; vLLM models are server-managed)."""
    try:
        result = await model_manager.load_model(
            model=request.model,
            backend=request.backend,
            keep_alive=request.keep_alive,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error loading model %s", request.model)
        raise HTTPException(status_code=500, detail=f"Failed to load model: {e}")
    return result


@router.post("/unload")
async def unload_model(request: UnloadModelRequest, user=Depends(get_optional_user)):
    """Unload a model from memory."""
    try:
        result = await model_manager.unload_model(
            model=request.model,
            backend=request.backend,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error unloading model %s", request.model)
        raise HTTPException(status_code=500, detail=f"Failed to unload model: {e}")
    return result


@router.patch("/config")
async def update_config(request: ModelConfigRequest, user=Depends(get_optional_user)):
    """Update active model/context-length/keep-alive settings."""
    _active_config.update(request.model_dump(exclude_none=True))
    return {"status": "ok", "config": _active_config}


@router.get("/config")
async def get_config(user=Depends(get_optional_user)):
    """Get the current active model configuration."""
    return _active_config


@router.get("/system-resources")
async def system_resources(user=Depends(get_optional_user)):
    """Get system resource information (RAM, CPU, GPU)."""
    try:
        return await model_manager.get_system_resources()
    except Exception as e:
        logger.exception("Failed to get system resources")
        raise HTTPException(status_code=500, detail=f"Failed to get system resources: {e}")


@router.get("/recommended")
async def recommended_models(user=Depends(get_optional_user)):
    """Get model recommendations based on system resources."""
    try:
        recommendations = await model_manager.recommend_models()
    except Exception as e:
        logger.exception("Failed to generate model recommendations")
        raise HTTPException(status_code=502, detail=f"Failed to generate recommendations: {e}")
    return {"models": recommendations, "count": len(recommendations)}

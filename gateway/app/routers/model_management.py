"""Model management endpoints: discovery, load/unload, config, system resources."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.model_manager import model_manager

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


# In-memory active config (per-session; a real deployment would persist this)
_active_config: dict[str, Any] = {
    "model": "",
    "backend": "vllm",
    "context_length": 8192,
    "keep_alive": "5m",
}


@router.get("/available")
async def list_available_models():
    """List all models from both backends with metadata."""
    models = await model_manager.list_available_models()
    return {"models": models, "count": len(models)}


@router.get("/loaded")
async def list_loaded_models():
    """List currently loaded models."""
    models = await model_manager.list_loaded_models()
    return {"models": models, "count": len(models)}


@router.post("/load")
async def load_model(request: LoadModelRequest):
    """Load a model into memory (llama.cpp only; vLLM models are server-managed)."""
    result = await model_manager.load_model(
        model=request.model,
        backend=request.backend,
        keep_alive=request.keep_alive,
    )
    return result


@router.post("/unload")
async def unload_model(request: UnloadModelRequest):
    """Unload a model from memory."""
    result = await model_manager.unload_model(
        model=request.model,
        backend=request.backend,
    )
    return result


@router.patch("/config")
async def update_config(request: ModelConfigRequest):
    """Update active model/context-length/keep-alive settings."""
    if request.model is not None:
        _active_config["model"] = request.model
    if request.backend is not None:
        _active_config["backend"] = request.backend
    if request.context_length is not None:
        _active_config["context_length"] = request.context_length
    if request.keep_alive is not None:
        _active_config["keep_alive"] = request.keep_alive

    return {"status": "ok", "config": _active_config}


@router.get("/config")
async def get_config():
    """Get the current active model configuration."""
    return _active_config


@router.get("/system-resources")
async def system_resources():
    """Get system resource information (RAM, CPU, GPU)."""
    return model_manager.get_system_resources()


@router.get("/recommended")
async def recommended_models():
    """Get model recommendations based on system resources."""
    recommendations = await model_manager.recommend_models()
    return {"models": recommendations, "count": len(recommendations)}

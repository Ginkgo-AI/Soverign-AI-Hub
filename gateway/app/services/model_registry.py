"""Model Registry Service — Phase 7.

Full CRUD for model entries, directory scanning, HuggingFace download support.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_registry import Model

logger = logging.getLogger(__name__)

MODELS_DIR = "/models"

# Known GGUF quantization markers
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


def _detect_model_features(name: str) -> list[str]:
    """Heuristic feature detection from model name."""
    features: list[str] = ["chat"]
    lower = name.lower()
    if any(kw in lower for kw in ("code", "coder", "starcoder", "deepseek-coder")):
        features.append("code")
    if any(kw in lower for kw in ("vision", "llava", "minicpm-v")):
        features.append("vision")
    if any(kw in lower for kw in ("embed", "nomic", "bge", "e5")):
        features = ["embedding"]
    return features


def _estimate_params_from_name(name: str) -> str | None:
    """Try to extract parameter count from name like '7B', '13B', '70B'."""
    import re
    match = re.search(r"(\d+\.?\d*)[Bb]", name)
    if match:
        return f"{match.group(1)}B"
    return None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def list_models(
    db: AsyncSession,
    backend: str | None = None,
    status: str | None = None,
    quantization: str | None = None,
) -> list[Model]:
    """List models with optional filtering."""
    stmt = select(Model).order_by(Model.created_at.desc())
    if backend:
        stmt = stmt.where(Model.backend == backend)
    if status:
        stmt = stmt.where(Model.status == status)
    if quantization:
        stmt = stmt.where(Model.quantization == quantization)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_model(db: AsyncSession, model_id: uuid.UUID) -> Model | None:
    result = await db.execute(select(Model).where(Model.id == model_id))
    return result.scalar_one_or_none()


async def get_model_by_name(db: AsyncSession, name: str) -> Model | None:
    result = await db.execute(select(Model).where(Model.name == name))
    return result.scalar_one_or_none()


async def register_model(
    db: AsyncSession,
    name: str,
    backend: str,
    file_path: str,
    version: str = "1.0",
    quantization: str | None = None,
    parameters: dict | None = None,
) -> Model:
    """Register a new model in the registry."""
    # Auto-detect quantization if not provided
    if quantization is None:
        quantization = _detect_quantization(name) or _detect_quantization(file_path)

    # Build default parameters metadata
    if parameters is None:
        parameters = {}
    if "features" not in parameters:
        parameters["features"] = _detect_model_features(name)
    if "param_count" not in parameters:
        est = _estimate_params_from_name(name)
        if est:
            parameters["param_count"] = est
    if "file_size" not in parameters:
        try:
            p = Path(file_path)
            if p.is_file():
                parameters["file_size"] = p.stat().st_size
            elif p.is_dir():
                total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                parameters["file_size"] = total
        except OSError:
            pass

    model = Model(
        name=name,
        version=version,
        backend=backend,
        file_path=file_path,
        quantization=quantization,
        parameters=parameters,
        status="available",
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return model


async def update_model(
    db: AsyncSession, model_id: uuid.UUID, updates: dict
) -> Model | None:
    """Update model metadata."""
    model = await get_model(db, model_id)
    if model is None:
        return None
    for field, value in updates.items():
        if value is not None and hasattr(model, field):
            setattr(model, field, value)
    await db.flush()
    await db.refresh(model)
    return model


async def update_model_status(
    db: AsyncSession, model_id: uuid.UUID, status: str
) -> Model | None:
    """Update just the status field."""
    return await update_model(db, model_id, {"status": status})


async def delete_model(
    db: AsyncSession, model_id: uuid.UUID, delete_files: bool = False
) -> bool:
    """Remove model from registry and optionally from disk."""
    model = await get_model(db, model_id)
    if model is None:
        return False
    if delete_files:
        try:
            p = Path(model.file_path)
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                import shutil
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            logger.warning("Failed to delete model files at %s", model.file_path)
    await db.delete(model)
    await db.flush()
    return True


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------

async def scan_model_directory(
    db: AsyncSession, path: str = MODELS_DIR
) -> list[Model]:
    """Scan a directory for model files and auto-register discovered models."""
    discovered: list[Model] = []
    base = Path(path)
    if not base.exists():
        logger.warning("Model directory does not exist: %s", path)
        return discovered

    # Scan for GGUF files (llama.cpp)
    for gguf_file in base.rglob("*.gguf"):
        name = gguf_file.stem
        existing = await get_model_by_name(db, name)
        if existing:
            continue
        model = await register_model(
            db=db,
            name=name,
            backend="llama-cpp",
            file_path=str(gguf_file),
        )
        discovered.append(model)
        logger.info("Auto-registered GGUF model: %s", name)

    # Scan for HuggingFace model directories (contain config.json)
    for config_file in base.rglob("config.json"):
        model_dir = config_file.parent
        # Skip adapter directories
        if "adapter" in str(model_dir).lower():
            continue
        name = model_dir.name
        existing = await get_model_by_name(db, name)
        if existing:
            continue
        # Try to read config.json for metadata
        params: dict = {}
        try:
            with open(config_file) as f:
                hf_config = json.load(f)
            if "max_position_embeddings" in hf_config:
                params["context_window"] = hf_config["max_position_embeddings"]
            if "hidden_size" in hf_config:
                params["hidden_size"] = hf_config["hidden_size"]
            if "num_hidden_layers" in hf_config:
                params["num_layers"] = hf_config["num_hidden_layers"]
            if "architectures" in hf_config:
                params["architecture"] = hf_config["architectures"][0]
        except (json.JSONDecodeError, OSError):
            pass

        model = await register_model(
            db=db,
            name=name,
            backend="vllm",
            file_path=str(model_dir),
            parameters=params,
        )
        discovered.append(model)
        logger.info("Auto-registered HF model: %s", name)

    return discovered


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

async def download_model(
    source: str,
    destination: str = MODELS_DIR,
    filename: str | None = None,
) -> str:
    """Download a model from HuggingFace Hub or copy from local path.

    Returns the path where the model was saved.
    """
    src_path = Path(source)

    # Local copy
    if src_path.exists():
        import shutil

        dest = Path(destination) / src_path.name
        if src_path.is_file():
            os.makedirs(destination, exist_ok=True)
            shutil.copy2(str(src_path), str(dest))
        else:
            shutil.copytree(str(src_path), str(dest), dirs_exist_ok=True)
        return str(dest)

    # HuggingFace Hub download
    try:
        from huggingface_hub import hf_hub_download, snapshot_download
    except ImportError:
        raise RuntimeError(
            "huggingface_hub is not installed. Install it with: pip install huggingface-hub"
        )

    os.makedirs(destination, exist_ok=True)

    if filename:
        # Download a single file (e.g., a specific GGUF quantization)
        path = hf_hub_download(
            repo_id=source,
            filename=filename,
            local_dir=destination,
            local_dir_use_symlinks=False,
        )
        return path
    else:
        # Download the full repo
        path = snapshot_download(
            repo_id=source,
            local_dir=os.path.join(destination, source.split("/")[-1]),
            local_dir_use_symlinks=False,
        )
        return path

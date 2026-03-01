"""Model management service: discovery, loading/unloading, system resources, recommendations."""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
import psutil

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    id: str
    backend: str
    size_bytes: int | None = None
    parameter_count: str | None = None
    quantization: str | None = None
    family: str | None = None
    loaded: bool = False
    context_length: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "backend": self.backend,
            "size_bytes": self.size_bytes,
            "parameter_count": self.parameter_count,
            "quantization": self.quantization,
            "family": self.family,
            "loaded": self.loaded,
            "context_length": self.context_length,
            **self.extra,
        }


@dataclass
class SystemResources:
    ram_total_gb: float
    ram_used_gb: float
    ram_available_gb: float
    cpu_count: int
    cpu_percent: float
    gpu_detected: bool = False
    gpu_name: str | None = None
    gpu_memory_total_gb: float | None = None
    gpu_memory_used_gb: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ram_total_gb": round(self.ram_total_gb, 2),
            "ram_used_gb": round(self.ram_used_gb, 2),
            "ram_available_gb": round(self.ram_available_gb, 2),
            "ram_percent": round(self.ram_used_gb / self.ram_total_gb * 100, 1)
            if self.ram_total_gb
            else 0,
            "cpu_count": self.cpu_count,
            "cpu_percent": self.cpu_percent,
            "gpu_detected": self.gpu_detected,
            "gpu_name": self.gpu_name,
            "gpu_memory_total_gb": self.gpu_memory_total_gb,
            "gpu_memory_used_gb": self.gpu_memory_used_gb,
        }


def _parse_model_metadata(model_id: str) -> dict[str, str | None]:
    """Extract family, quantization, and parameter count from model ID heuristics."""
    model_lower = model_id.lower()
    family = None
    quantization = None
    parameter_count = None

    # Detect family
    for f in ("llama", "mistral", "mixtral", "phi", "gemma", "qwen", "codellama", "deepseek"):
        if f in model_lower:
            family = f.capitalize()
            break

    # Detect quantization
    for q in ("q2_k", "q3_k_m", "q4_0", "q4_k_m", "q4_k_s", "q5_0", "q5_k_m", "q6_k", "q8_0"):
        if q in model_lower:
            quantization = q.upper()
            break
    if not quantization:
        for q in ("fp16", "fp32", "int8", "int4", "awq", "gptq", "gguf"):
            if q in model_lower:
                quantization = q.upper()
                break

    # Detect parameter count
    import re

    match = re.search(r"(\d+\.?\d*)[bB]", model_id)
    if match:
        parameter_count = f"{match.group(1)}B"

    return {"family": family, "quantization": quantization, "parameter_count": parameter_count}


class ModelManager:
    """Manages model discovery, loading/unloading across vLLM and llama.cpp backends."""

    def __init__(self):
        self._clients: dict[str, httpx.AsyncClient] = {}

    def _get_client(self, backend: str) -> httpx.AsyncClient:
        if backend not in self._clients:
            if backend == "vllm":
                base_url = settings.vllm_base_url
            elif backend == "llama-cpp":
                base_url = settings.llama_cpp_base_url
            else:
                raise ValueError(f"Unknown backend: {backend}")
            self._clients[backend] = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        return self._clients[backend]

    async def list_available_models(self) -> list[dict[str, Any]]:
        """Query both backends for available models with metadata."""
        models: list[dict[str, Any]] = []

        for backend in ("vllm", "llama-cpp"):
            try:
                client = self._get_client(backend)
                response = await client.get("/models")
                response.raise_for_status()
                data = response.json()
                for m in data.get("data", []):
                    model_id = m.get("id", "")
                    metadata = _parse_model_metadata(model_id)
                    info = ModelInfo(
                        id=model_id,
                        backend=backend,
                        loaded=True,  # If listed by the server, it's available/loaded
                        context_length=m.get("max_model_len") or m.get("context_length"),
                        family=metadata["family"],
                        quantization=metadata["quantization"],
                        parameter_count=metadata["parameter_count"],
                    )
                    models.append(info.to_dict())
            except httpx.HTTPError:
                logger.debug("Backend %s unavailable for model listing", backend)
            except Exception:
                logger.exception("Error listing models from %s", backend)

        return models

    async def list_loaded_models(self) -> list[dict[str, Any]]:
        """List currently loaded/active models. For vLLM, all listed models are loaded."""
        # Same as available for OpenAI-compatible servers — loaded models are the ones served
        return await self.list_available_models()

    async def load_model(
        self,
        model: str,
        backend: str = "llama-cpp",
        keep_alive: str = "5m",
    ) -> dict[str, Any]:
        """Load a model into memory. Only llama.cpp supports dynamic loading via Ollama endpoints."""
        if backend == "vllm":
            return {
                "status": "info",
                "message": "vLLM models are server-managed. Restart the vLLM server to change models.",
            }

        # llama.cpp with Ollama-compatible endpoint: POST /api/generate with keep_alive
        try:
            client = self._get_client(backend)
            response = await client.post(
                "/api/generate",
                json={"model": model, "keep_alive": keep_alive, "prompt": ""},
                timeout=120.0,
            )
            if response.status_code < 400:
                return {"status": "ok", "message": f"Model {model} loaded with keep_alive={keep_alive}"}
            return {"status": "error", "message": f"Backend returned {response.status_code}"}
        except httpx.HTTPError as e:
            return {"status": "error", "message": str(e)}

    async def unload_model(self, model: str, backend: str = "llama-cpp") -> dict[str, Any]:
        """Unload a model from memory by setting keep_alive=0."""
        if backend == "vllm":
            return {
                "status": "info",
                "message": "vLLM models cannot be unloaded dynamically.",
            }

        try:
            client = self._get_client(backend)
            response = await client.post(
                "/api/generate",
                json={"model": model, "keep_alive": "0", "prompt": ""},
                timeout=30.0,
            )
            if response.status_code < 400:
                return {"status": "ok", "message": f"Model {model} unloaded"}
            return {"status": "error", "message": f"Backend returned {response.status_code}"}
        except httpx.HTTPError as e:
            return {"status": "error", "message": str(e)}

    def get_system_resources(self) -> dict[str, Any]:
        """Get current system resource usage."""
        mem = psutil.virtual_memory()
        resources = SystemResources(
            ram_total_gb=mem.total / (1024**3),
            ram_used_gb=mem.used / (1024**3),
            ram_available_gb=mem.available / (1024**3),
            cpu_count=psutil.cpu_count(logical=True) or 0,
            cpu_percent=psutil.cpu_percent(interval=0.1),
        )

        # Try to detect NVIDIA GPU
        try:
            import subprocess

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    resources.gpu_detected = True
                    resources.gpu_name = parts[0].strip()
                    resources.gpu_memory_total_gb = float(parts[1].strip()) / 1024
                    resources.gpu_memory_used_gb = float(parts[2].strip()) / 1024
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

        return resources.to_dict()

    async def recommend_models(self) -> list[dict[str, Any]]:
        """Recommend models based on available system resources."""
        resources = self.get_system_resources()
        available_ram = resources["ram_available_gb"]
        gpu_mem = resources.get("gpu_memory_total_gb")

        models = await self.list_available_models()
        recommendations = []

        for model in models:
            param_str = model.get("parameter_count", "")
            quant = model.get("quantization", "")

            # Estimate memory requirement from parameter count
            estimated_gb = _estimate_model_memory(param_str, quant)

            if estimated_gb is None:
                fit = "unknown"
                fit_score = 50
            elif gpu_mem and estimated_gb <= gpu_mem * 0.8:
                fit = "good"
                fit_score = 90
            elif estimated_gb <= available_ram * 0.6:
                fit = "good"
                fit_score = 85
            elif estimated_gb <= available_ram * 0.85:
                fit = "moderate"
                fit_score = 60
            else:
                fit = "poor"
                fit_score = 20

            recommendations.append(
                {
                    **model,
                    "estimated_memory_gb": round(estimated_gb, 1) if estimated_gb else None,
                    "fit": fit,
                    "fit_score": fit_score,
                }
            )

        recommendations.sort(key=lambda r: r["fit_score"], reverse=True)
        return recommendations

    async def close(self):
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()


def _estimate_model_memory(param_str: str | None, quantization: str | None) -> float | None:
    """Rough estimate of model memory in GB based on parameter count and quantization."""
    if not param_str:
        return None

    try:
        params_b = float(param_str.replace("B", "").replace("b", ""))
    except ValueError:
        return None

    # Bits per parameter based on quantization
    bits = 16.0  # default FP16
    if quantization:
        q = quantization.upper()
        if "Q4" in q or "INT4" in q:
            bits = 4.5
        elif "Q5" in q:
            bits = 5.5
        elif "Q6" in q:
            bits = 6.5
        elif "Q8" in q or "INT8" in q:
            bits = 8.0
        elif "Q3" in q:
            bits = 3.5
        elif "Q2" in q:
            bits = 2.5
        elif "FP32" in q:
            bits = 32.0
        elif "AWQ" in q or "GPTQ" in q:
            bits = 4.0

    # bytes = params * bits / 8, plus ~10% overhead
    return params_b * bits / 8 * 1.1


# Singleton
model_manager = ModelManager()

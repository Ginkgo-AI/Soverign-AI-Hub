from fastapi import APIRouter

from app.services.llm import llm_backend

router = APIRouter()


@router.get("/models")
async def list_models():
    """List available models from all backends. OpenAI-compatible."""
    all_models = []

    for backend in ("vllm", "llama-cpp"):
        try:
            result = await llm_backend.list_models(backend)
            for model in result.get("data", []):
                model["_backend"] = backend
                all_models.append(model)
        except Exception:
            pass

    return {"object": "list", "data": all_models}

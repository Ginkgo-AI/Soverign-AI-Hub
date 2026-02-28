from fastapi import APIRouter

from app.services.llm import llm_backend

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "sovereign-ai-gateway"}


@router.get("/healthz")
async def healthz():
    """Detailed health check for all dependencies."""
    checks = {}

    # Check database
    try:
        from app.database import engine

        async with engine.begin() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Check LLM backends
    for backend in ("vllm", "llama-cpp"):
        checks[backend] = "ok" if await llm_backend.health_check(backend) else "unavailable"

    all_ok = checks.get("postgres") == "ok" and any(
        checks.get(b) == "ok" for b in ("vllm", "llama-cpp")
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }

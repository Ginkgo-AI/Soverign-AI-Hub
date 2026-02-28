from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.audit import AuditMiddleware
from app.routers import (
    admin,
    agents,
    audio,
    auth,
    chat,
    code,
    collections,
    conversations,
    documents,
    edge,
    embeddings,
    health,
    images,
    models,
    search,
    system_prompts,
    training,
    vision,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.database import engine

    async with engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))

    # Register built-in agent tools
    from app.services.tool_executor import register_builtin_tools

    register_builtin_tools()

    yield
    # Shutdown
    from app.services.llm import llm_backend
    from app.services.vector_store import vector_store
    from app.services.whisper import whisper_client
    from app.services.tts import tts_client
    from app.services.image_gen import image_gen_client

    # Flush any remaining audit records
    from app.services.audit import _flush_buffer

    await _flush_buffer()

    await llm_backend.close()
    await vector_store.close()
    await whisper_client.close()
    await tts_client.close()
    await image_gen_client.close()
    await engine.dispose()


app = FastAPI(
    title="Sovereign AI Hub",
    description="Air-gapped, locally-run AI platform API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-ID", "X-Request-ID"],
)

# Audit logging (Phase 6: full structured audit to PostgreSQL)
app.add_middleware(AuditMiddleware)

# Air-gap enforcement (Phase 6)
if settings.airgap_mode:
    from app.middleware.airgap import AirgapMiddleware

    app.add_middleware(AirgapMiddleware)

# Auth
app.include_router(auth.router, prefix="/api", tags=["Auth"])

# OpenAI-compatible endpoints
app.include_router(chat.router, prefix="/v1", tags=["Chat"])
app.include_router(models.v1_router, prefix="/v1", tags=["Models"])
app.include_router(embeddings.router, prefix="/v1", tags=["Embeddings"])

# Application endpoints
app.include_router(health.router)
app.include_router(conversations.router, prefix="/api", tags=["Conversations"])
app.include_router(system_prompts.router, prefix="/api", tags=["System Prompts"])
app.include_router(collections.router, prefix="/api", tags=["Collections"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(search.router, prefix="/api", tags=["Search"])
app.include_router(agents.router, prefix="/api", tags=["Agents"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# Multimodal endpoints (Phase 4)
app.include_router(vision.router, prefix="/v1", tags=["Vision"])
app.include_router(audio.router, prefix="/v1", tags=["Audio"])
app.include_router(images.generation_router, prefix="/v1", tags=["Images"])
app.include_router(images.gallery_router, prefix="/api", tags=["Images"])

# Code Assistant endpoints (Phase 5)
app.include_router(code.router, prefix="/api", tags=["Code"])

# Model Management & Fine-Tuning endpoints (Phase 7)
app.include_router(models.router, prefix="/api", tags=["Model Registry"])
app.include_router(training.router, prefix="/api", tags=["Training"])

# Edge Device Management endpoints (Phase 8)
app.include_router(edge.router, prefix="/api", tags=["Edge Devices"])

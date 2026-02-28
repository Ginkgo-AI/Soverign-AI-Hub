from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.audit import AuditMiddleware
from app.routers import (
    admin,
    agents,
    auth,
    chat,
    collections,
    conversations,
    documents,
    embeddings,
    health,
    models,
    search,
    system_prompts,
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

    await llm_backend.close()
    await vector_store.close()
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

# Audit logging
app.add_middleware(AuditMiddleware)

# Auth
app.include_router(auth.router, prefix="/api", tags=["Auth"])

# OpenAI-compatible endpoints
app.include_router(chat.router, prefix="/v1", tags=["Chat"])
app.include_router(models.router, prefix="/v1", tags=["Models"])
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

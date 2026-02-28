from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.audit import AuditMiddleware
from app.routers import admin, agents, chat, collections, documents, embeddings, health, models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.database import engine

    # Verify database connection
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text("SELECT 1")
        )
    yield
    # Shutdown
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
)

# Audit logging
app.add_middleware(AuditMiddleware)

# Routers
app.include_router(health.router)
app.include_router(chat.router, prefix="/v1", tags=["Chat"])
app.include_router(models.router, prefix="/v1", tags=["Models"])
app.include_router(embeddings.router, prefix="/v1", tags=["Embeddings"])
app.include_router(collections.router, prefix="/api", tags=["Collections"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(agents.router, prefix="/api", tags=["Agents"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

"""Pydantic schemas for RAG collections, documents, and search."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ─── Collection schemas ───────────────────────────────────────────────

class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    classification_level: str = "UNCLASSIFIED"
    embedding_model: str = "nomic-embed-text"
    chunk_size: int = Field(default=512, ge=64, le=4096)
    chunk_overlap: int = Field(default=50, ge=0, le=1024)


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    classification_level: str | None = None
    chunk_size: int | None = Field(default=None, ge=64, le=4096)
    chunk_overlap: int | None = Field(default=None, ge=0, le=1024)


class CollectionResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    owner_id: uuid.UUID
    classification_level: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
    total: int


class CollectionPermissionCreate(BaseModel):
    role: str
    access_level: str = "read"


# ─── Document schemas ─────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str
    message: str


class DocumentResponse(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    metadata_: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


# ─── Search schemas ───────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    collection_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    use_hybrid: bool = True


class Citation(BaseModel):
    document_name: str
    page_number: int | None = None
    chunk_index: int
    excerpt: str
    score: float


class SearchResult(BaseModel):
    content: str
    score: float
    document_id: uuid.UUID | None = None
    document_name: str | None = None
    chunk_index: int = 0
    page_number: int | None = None
    metadata: dict[str, Any] | None = None


class SearchResponse(BaseModel):
    query: str
    answer: str | None = None
    results: list[SearchResult]
    citations: list[Citation]
    total_results: int

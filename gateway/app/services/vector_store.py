"""Qdrant vector store client wrapper.

Adapted from Metis_2's ChromaDB-based VectorStoreService to target Qdrant.
Provides collection CRUD, batch upsert, filtered search, and deletion.
"""

import logging
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    HasIdCondition,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)


def _qdrant_collection_name(collection_id: uuid.UUID) -> str:
    """Convert a PostgreSQL collection UUID into a Qdrant collection name."""
    return f"col_{str(collection_id).replace('-', '_')}"


class VectorStoreService:
    """Async wrapper around the Qdrant vector database."""

    def __init__(self) -> None:
        self._client: AsyncQdrantClient | None = None

    async def _get_client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                timeout=60,
            )
        return self._client

    # ── Collection management ──────────────────────────────────────────

    async def create_collection(
        self,
        collection_id: uuid.UUID,
        vector_size: int = 768,
        distance: Distance = Distance.COSINE,
    ) -> None:
        """Create a Qdrant collection for the given PostgreSQL collection UUID."""
        client = await self._get_client()
        name = _qdrant_collection_name(collection_id)

        exists = await client.collection_exists(name)
        if exists:
            logger.info("Qdrant collection '%s' already exists", name)
            return

        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )

        # Payload indices for filtered search
        await client.create_payload_index(name, "collection_id", models.PayloadSchemaType.KEYWORD)
        await client.create_payload_index(name, "document_id", models.PayloadSchemaType.KEYWORD)
        await client.create_payload_index(name, "classification_level", models.PayloadSchemaType.KEYWORD)

        logger.info("Created Qdrant collection '%s' (dim=%d)", name, vector_size)

    async def delete_collection(self, collection_id: uuid.UUID) -> None:
        """Delete the Qdrant collection for a PostgreSQL collection."""
        client = await self._get_client()
        name = _qdrant_collection_name(collection_id)
        try:
            await client.delete_collection(name)
            logger.info("Deleted Qdrant collection '%s'", name)
        except Exception:
            logger.warning("Failed to delete Qdrant collection '%s'", name, exc_info=True)

    # ── Upsert vectors ─────────────────────────────────────────────────

    async def upsert_vectors(
        self,
        collection_id: uuid.UUID,
        points: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """Batch-upsert vectors into a Qdrant collection.

        Each dict in *points* must have:
          - ``id``: str (UUID) — point ID
          - ``vector``: list[float]
          - ``payload``: dict with at least ``document_id``, ``content``, ``chunk_index``
        """
        client = await self._get_client()
        name = _qdrant_collection_name(collection_id)
        total_upserted = 0

        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            qdrant_points = [
                PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p["payload"],
                )
                for p in batch
            ]
            await client.upsert(collection_name=name, points=qdrant_points)
            total_upserted += len(batch)

        logger.info("Upserted %d points into '%s'", total_upserted, name)
        return total_upserted

    # ── Search ─────────────────────────────────────────────────────────

    async def search(
        self,
        collection_id: uuid.UUID,
        query_vector: list[float],
        top_k: int = 10,
        score_threshold: float = 0.0,
        classification_level: str | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Similarity search with optional metadata filters.

        Returns list of dicts with ``id``, ``score``, ``content``, ``metadata``.
        """
        client = await self._get_client()
        name = _qdrant_collection_name(collection_id)

        # Build filter conditions
        conditions: list[models.Condition] = []
        if classification_level:
            conditions.append(
                FieldCondition(key="classification_level", match=MatchValue(value=classification_level))
            )
        if document_ids:
            conditions.append(
                FieldCondition(key="document_id", match=models.MatchAny(any=document_ids))
            )

        query_filter = Filter(must=conditions) if conditions else None

        hits = await client.search(
            collection_name=name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )

        results: list[dict[str, Any]] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "content": payload.get("content", ""),
                    "metadata": {
                        "document_id": payload.get("document_id"),
                        "document_name": payload.get("document_name"),
                        "chunk_index": payload.get("chunk_index", 0),
                        "page_number": payload.get("page_number"),
                        "collection_id": payload.get("collection_id"),
                        "classification_level": payload.get("classification_level"),
                        **{k: v for k, v in payload.items() if k not in (
                            "content", "document_id", "document_name",
                            "chunk_index", "page_number", "collection_id",
                            "classification_level",
                        )},
                    },
                }
            )

        return results

    # ── Deletion ───────────────────────────────────────────────────────

    async def delete_by_document_id(
        self,
        collection_id: uuid.UUID,
        document_id: str,
    ) -> None:
        """Delete all vectors belonging to a given document."""
        client = await self._get_client()
        name = _qdrant_collection_name(collection_id)

        await client.delete(
            collection_name=name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                )
            ),
        )
        logger.info("Deleted vectors for document '%s' from '%s'", document_id, name)

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


# Singleton
vector_store = VectorStoreService()

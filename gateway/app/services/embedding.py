"""Embedding service — calls our local embedding model via vLLM or llama.cpp."""

import logging
from typing import Any

from app.services.llm import llm_backend

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_BACKEND = "vllm"
BATCH_SIZE = 64  # max texts per request


class EmbeddingService:
    """Generate embeddings using the local vLLM / llama-cpp backend."""

    @staticmethod
    async def embed_text(
        text: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
        backend: str = DEFAULT_BACKEND,
    ) -> list[float]:
        """Embed a single text string and return the vector."""
        result = await llm_backend.create_embedding(text, model=model, backend=backend)
        return _extract_single(result)

    @staticmethod
    async def embed_texts(
        texts: list[str],
        model: str = DEFAULT_EMBEDDING_MODEL,
        backend: str = DEFAULT_BACKEND,
    ) -> list[list[float]]:
        """Embed a list of texts. Handles batching internally."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            try:
                result = await llm_backend.create_embedding(batch, model=model, backend=backend)
                batch_embeddings = _extract_batch(result, expected=len(batch))
                all_embeddings.extend(batch_embeddings)
            except Exception:
                logger.exception("Embedding batch failed (start=%d)", start)
                raise

        if len(all_embeddings) != len(texts):
            raise ValueError(
                f"Embedding count mismatch: got {len(all_embeddings)}, expected {len(texts)}"
            )
        return all_embeddings

    @staticmethod
    async def get_dimension(
        model: str = DEFAULT_EMBEDDING_MODEL,
        backend: str = DEFAULT_BACKEND,
    ) -> int:
        """Return the embedding dimension by sending a probe string."""
        vec = await EmbeddingService.embed_text("dimension probe", model=model, backend=backend)
        return len(vec)


# ── helpers ────────────────────────────────────────────────────────────

def _extract_single(response: dict[str, Any]) -> list[float]:
    """Pull the first embedding vector from an OpenAI-compatible response."""
    data = response.get("data", [])
    if not data:
        raise ValueError("Empty embedding response")
    return data[0]["embedding"]


def _extract_batch(response: dict[str, Any], expected: int) -> list[list[float]]:
    """Pull all embedding vectors, sorted by index."""
    data = response.get("data", [])
    if len(data) != expected:
        raise ValueError(f"Expected {expected} embeddings, got {len(data)}")
    sorted_data = sorted(data, key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in sorted_data]

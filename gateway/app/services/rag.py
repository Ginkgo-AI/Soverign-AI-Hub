"""RAG pipeline — hybrid search (Qdrant vector + PostgreSQL FTS) with RRF.

Adapted from Metis_2's core/rag.py. Key changes:
  - Qdrant for vector search (not ChromaDB)
  - PostgreSQL full-text search for BM25 component (not Neo4j)
  - Reciprocal Rank Fusion to merge results
  - Citations with document name, page number, chunk excerpt
  - Uses local LLM backend via gateway LLM service
"""

import logging
import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection import Chunk, Collection, Document
from app.schemas.rag import Citation, SearchRequest, SearchResponse, SearchResult
from app.services.embedding import EmbeddingService
from app.services.llm import llm_backend
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

RRF_K = 60  # Reciprocal Rank Fusion constant
DEFAULT_TOP_K = 5
FTS_CANDIDATE_MULTIPLIER = 3  # Fetch more FTS candidates for better fusion

DEFAULT_PROMPT_TEMPLATE = """You are a helpful AI assistant that answers questions using the provided context.
Base your answers on the retrieved context. If the context does not contain enough information, say so clearly.
Always cite which documents and sections your answer draws from.

## Retrieved Context:
{context}

## User Question:
{question}

## Instructions:
- Answer the question based on the context above.
- Reference specific documents when possible.
- If the context is insufficient, acknowledge the limitation.
- Use clear, well-structured Markdown formatting.
"""


# ── Reciprocal Rank Fusion ─────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: list[list[dict[str, Any]]],
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    Each item in a ranked list must have an ``id`` key.
    Returns a single list sorted by fused score, highest first.
    """
    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            # Keep whichever copy has more metadata
            if item_id not in items or len(item.get("metadata", {})) > len(
                items[item_id].get("metadata", {})
            ):
                items[item_id] = item

    # Attach fused score
    for item_id, item in items.items():
        item["rrf_score"] = scores[item_id]

    return sorted(items.values(), key=lambda x: x["rrf_score"], reverse=True)


# ── PostgreSQL full-text search ────────────────────────────────────────

async def postgres_fts_search(
    db: AsyncSession,
    query: str,
    collection_ids: list[uuid.UUID] | None = None,
    top_k: int = 15,
) -> list[dict[str, Any]]:
    """Run PostgreSQL full-text search on the chunks table.

    Uses ``to_tsvector`` / ``plainto_tsquery`` and ``ts_rank_cd`` for scoring.
    Returns results in a format compatible with the vector search output.
    """
    ts_query = func.plainto_tsquery("english", query)

    stmt = (
        select(
            Chunk.id,
            Chunk.content,
            Chunk.chunk_index,
            Chunk.page_number,
            Chunk.document_id,
            Chunk.metadata_,
            func.ts_rank_cd(func.to_tsvector("english", Chunk.content), ts_query).label("rank"),
        )
        .where(func.to_tsvector("english", Chunk.content).op("@@")(ts_query))
    )

    # Filter by collection_ids through document -> collection relationship
    if collection_ids:
        stmt = stmt.join(Document, Chunk.document_id == Document.id).where(
            Document.collection_id.in_(collection_ids)
        )

    stmt = stmt.order_by(text("rank DESC")).limit(top_k)

    result = await db.execute(stmt)
    rows = result.all()

    fts_results: list[dict[str, Any]] = []
    for row in rows:
        fts_results.append(
            {
                "id": str(row.id),
                "score": float(row.rank),
                "content": row.content,
                "metadata": {
                    "document_id": str(row.document_id),
                    "chunk_index": row.chunk_index,
                    "page_number": row.page_number,
                    **(row.metadata_ or {}),
                },
            }
        )

    return fts_results


# ── Deduplication ──────────────────────────────────────────────────────

def _deduplicate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by normalised text, keeping the highest-scored variant."""
    seen: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        normalised = " ".join(chunk.get("content", "").split())
        score = chunk.get("rrf_score", chunk.get("score", 0.0))
        if normalised not in seen:
            seen[normalised] = chunk
        else:
            existing_score = seen[normalised].get("rrf_score", seen[normalised].get("score", 0.0))
            if score > existing_score:
                seen[normalised] = chunk
    return list(seen.values())


# ── Citation extraction ────────────────────────────────────────────────

def _extract_citations(results: list[dict[str, Any]]) -> list[Citation]:
    """Build citation objects from search results."""
    citations: list[Citation] = []
    for result in results:
        meta = result.get("metadata", {})
        content = result.get("content", "")
        excerpt = content[:200] + "..." if len(content) > 200 else content

        citations.append(
            Citation(
                document_name=meta.get("document_name", "Unknown"),
                page_number=meta.get("page_number"),
                chunk_index=meta.get("chunk_index", 0),
                excerpt=excerpt,
                score=result.get("rrf_score", result.get("score", 0.0)),
            )
        )
    return citations


# ── Public API ─────────────────────────────────────────────────────────

async def hybrid_search(
    db: AsyncSession,
    vector_store: VectorStoreService,
    request: SearchRequest,
    user_id: uuid.UUID | None = None,
) -> SearchResponse:
    """Execute hybrid search: Qdrant vector + PostgreSQL FTS merged via RRF.

    Optionally generates an LLM answer when there are results.
    """
    query = request.query
    collection_ids = request.collection_ids
    top_k = request.top_k
    use_hybrid = request.use_hybrid

    logger.info("Hybrid search: query='%s', collections=%s, top_k=%d", query[:60], collection_ids, top_k)

    # 1. Generate query embedding
    query_embedding = await EmbeddingService.embed_text(query)

    # 2. Vector search across requested collections
    vector_results: list[dict[str, Any]] = []
    if collection_ids:
        for cid in collection_ids:
            hits = await vector_store.search(
                collection_id=cid,
                query_vector=query_embedding,
                top_k=top_k * FTS_CANDIDATE_MULTIPLIER,
                score_threshold=request.score_threshold,
            )
            vector_results.extend(hits)
    else:
        # If no collection specified, we only do FTS (vector search needs a collection)
        logger.info("No collection_ids specified — skipping vector search")

    # Sort vector results by score descending (they come from multiple collections)
    vector_results.sort(key=lambda x: x["score"], reverse=True)

    # 3. PostgreSQL full-text search
    fts_results: list[dict[str, Any]] = []
    if use_hybrid:
        fts_results = await postgres_fts_search(
            db,
            query,
            collection_ids=collection_ids,
            top_k=top_k * FTS_CANDIDATE_MULTIPLIER,
        )

    # 4. Merge via RRF
    if vector_results and fts_results:
        merged = reciprocal_rank_fusion([vector_results, fts_results])
    elif vector_results:
        merged = vector_results
    elif fts_results:
        merged = fts_results
    else:
        merged = []

    # 5. Deduplicate
    merged = _deduplicate_chunks(merged)

    # 6. Trim to top_k
    merged = merged[:top_k]

    # 7. Enrich with document names from the DB
    await _enrich_document_names(db, merged)

    # 8. Extract citations
    citations = _extract_citations(merged)

    # 9. Build search results
    search_results = [
        SearchResult(
            content=r["content"],
            score=r.get("rrf_score", r.get("score", 0.0)),
            document_id=_safe_uuid(r["metadata"].get("document_id")),
            document_name=r["metadata"].get("document_name"),
            chunk_index=r["metadata"].get("chunk_index", 0),
            page_number=r["metadata"].get("page_number"),
            metadata=r.get("metadata"),
        )
        for r in merged
    ]

    # 10. Optional LLM answer generation
    answer = None
    if merged:
        answer = await _generate_answer(query, merged)

    return SearchResponse(
        query=query,
        answer=answer,
        results=search_results,
        citations=citations,
        total_results=len(search_results),
    )


# ── Helpers ────────────────────────────────────────────────────────────

async def _enrich_document_names(
    db: AsyncSession,
    results: list[dict[str, Any]],
) -> None:
    """Look up document filenames from PostgreSQL and inject into metadata."""
    doc_ids: set[str] = set()
    for r in results:
        did = r.get("metadata", {}).get("document_id")
        if did:
            doc_ids.add(did)

    if not doc_ids:
        return

    uuids = [uuid.UUID(d) for d in doc_ids if d]
    stmt = select(Document.id, Document.filename).where(Document.id.in_(uuids))
    rows = await db.execute(stmt)
    name_map = {str(row.id): row.filename for row in rows}

    for r in results:
        did = r.get("metadata", {}).get("document_id")
        if did and did in name_map:
            r["metadata"]["document_name"] = name_map[did]


async def _generate_answer(
    query: str,
    chunks: list[dict[str, Any]],
) -> str | None:
    """Use the local LLM to generate a contextual answer."""
    context_parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("document_name", "Unknown")
        page = meta.get("page_number")
        page_str = f" (page {page})" if page else ""
        context_parts.append(f"[{i}] {source}{page_str}:\n{chunk['content']}")

    context = "\n\n---\n\n".join(context_parts)
    prompt_text = DEFAULT_PROMPT_TEMPLATE.format(context=context, question=query)

    try:
        response = await llm_backend.chat_completion(
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.3,
            max_tokens=2048,
        )
        answer = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return answer if answer else None
    except Exception:
        logger.exception("LLM answer generation failed")
        return None


def _safe_uuid(val: Any) -> uuid.UUID | None:
    if val is None:
        return None
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return None

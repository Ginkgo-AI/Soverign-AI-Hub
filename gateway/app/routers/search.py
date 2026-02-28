"""RAG search endpoint — hybrid vector + FTS search with citations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.rag import SearchRequest, SearchResponse
from app.services.rag import hybrid_search
from app.services.vector_store import vector_store

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Execute a RAG search across collections.

    Combines Qdrant vector similarity with PostgreSQL full-text search
    using Reciprocal Rank Fusion, then optionally generates an LLM answer
    grounded in the retrieved context.

    **Request body:**
    - ``query``: natural-language question
    - ``collection_ids``: (optional) restrict search to specific collections
    - ``top_k``: number of results to return (default 5)
    - ``score_threshold``: minimum vector similarity score (default 0.0)
    - ``use_hybrid``: combine vector + FTS search (default true)
    """
    return await hybrid_search(
        db=db,
        vector_store=vector_store,
        request=body,
        user_id=user.id,
    )

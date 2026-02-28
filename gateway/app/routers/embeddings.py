from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm import llm_backend

router = APIRouter()


class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str = ""


@router.post("/embeddings")
async def create_embedding(request: EmbeddingRequest):
    """OpenAI-compatible embedding endpoint."""
    result = await llm_backend.create_embedding(
        input_text=request.input,
        model=request.model,
    )
    return result

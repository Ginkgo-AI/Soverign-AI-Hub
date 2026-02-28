"""RAG collection management endpoints. Fleshed out in Phase 2."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/collections")
async def list_collections():
    return {"collections": [], "total": 0}


@router.post("/collections")
async def create_collection():
    return {"status": "not_implemented", "message": "RAG collections coming in Phase 2"}

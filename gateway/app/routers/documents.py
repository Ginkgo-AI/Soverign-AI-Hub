"""Document upload and processing endpoints. Fleshed out in Phase 2."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/documents/upload")
async def upload_document():
    return {"status": "not_implemented", "message": "Document upload coming in Phase 2"}

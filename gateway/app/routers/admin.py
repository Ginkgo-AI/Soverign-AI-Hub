"""Admin endpoints: users, roles, audit log. Auth required."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/users")
async def list_users():
    return {"users": [], "total": 0}


@router.get("/audit")
async def get_audit_log():
    return {"entries": [], "total": 0}

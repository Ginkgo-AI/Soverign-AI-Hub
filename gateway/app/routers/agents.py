"""Agent management and execution endpoints. Fleshed out in Phase 3."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/agents")
async def list_agents():
    return {"agents": [], "total": 0}


@router.post("/agents")
async def create_agent():
    return {"status": "not_implemented", "message": "Agent runtime coming in Phase 3"}


@router.post("/agents/{agent_id}/execute")
async def execute_agent(agent_id: str):
    return {"status": "not_implemented", "message": "Agent execution coming in Phase 3"}

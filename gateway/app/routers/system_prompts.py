"""System prompt library — save, list, and use reusable personas/system prompts."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.system_prompt import SystemPrompt
from app.models.user import User
from app.schemas.conversation import SystemPromptCreate, SystemPromptResponse

router = APIRouter()

# Seed defaults
DEFAULT_PROMPTS = [
    {
        "name": "General Assistant",
        "description": "Helpful, balanced AI assistant",
        "content": "You are a helpful AI assistant. Answer questions accurately and concisely.",
    },
    {
        "name": "Analyst",
        "description": "Structured analysis with evidence-based reasoning",
        "content": (
            "You are an intelligence analyst. Provide structured, evidence-based analysis. "
            "Clearly distinguish between facts, assessments, and assumptions. "
            "Rate confidence levels as high, moderate, or low."
        ),
    },
    {
        "name": "Technical Writer",
        "description": "Clear documentation and technical writing",
        "content": (
            "You are a technical writer. Produce clear, well-structured documentation. "
            "Use headings, bullet points, and tables where appropriate. "
            "Write for a technical audience that values precision."
        ),
    },
    {
        "name": "Code Assistant",
        "description": "Programming help with explanations",
        "content": (
            "You are an expert software engineer. Write clean, well-commented code. "
            "Explain your approach before writing code. Prefer simple, readable solutions. "
            "Always consider edge cases and error handling."
        ),
    },
]


@router.get("/system-prompts", response_model=list[SystemPromptResponse])
async def list_system_prompts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SystemPrompt).order_by(SystemPrompt.is_default.desc(), SystemPrompt.name)
    )
    prompts = result.scalars().all()

    # If no prompts exist, seed defaults
    if not prompts:
        for default in DEFAULT_PROMPTS:
            sp = SystemPrompt(
                name=default["name"],
                description=default["description"],
                content=default["content"],
                created_by=user.id,
                is_default=True,
            )
            db.add(sp)
        await db.flush()

        result = await db.execute(
            select(SystemPrompt).order_by(SystemPrompt.is_default.desc(), SystemPrompt.name)
        )
        prompts = result.scalars().all()

    return prompts


@router.post("/system-prompts", response_model=SystemPromptResponse, status_code=201)
async def create_system_prompt(
    body: SystemPromptCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sp = SystemPrompt(
        name=body.name,
        content=body.content,
        description=body.description,
        created_by=user.id,
    )
    db.add(sp)
    await db.flush()
    return sp


@router.get("/system-prompts/{prompt_id}", response_model=SystemPromptResponse)
async def get_system_prompt(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(SystemPrompt).where(SystemPrompt.id == prompt_id))
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return sp


@router.delete("/system-prompts/{prompt_id}", status_code=204)
async def delete_system_prompt(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(SystemPrompt).where(SystemPrompt.id == prompt_id))
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="System prompt not found")
    if sp.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default system prompts")
    await db.delete(sp)

"""Skills registry endpoints — catalog, full load, CRUD, activation."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, get_optional_user
from app.models.skill import Skill
from app.schemas.skill import (
    SkillCatalogListOut,
    SkillCatalogOut,
    SkillCreate,
    SkillFullOut,
    SkillUpdate,
)
from app.services.skill_service import activate_skill, get_skill_catalog, get_skill_full

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/skills", response_model=SkillCatalogListOut)
async def list_skills(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user),
):
    skills = await get_skill_catalog(db)
    if category:
        skills = [s for s in skills if s.category == category]
    return SkillCatalogListOut(
        skills=[SkillCatalogOut.model_validate(s) for s in skills],
        total=len(skills),
    )


@router.get("/skills/{skill_id}", response_model=SkillFullOut)
async def get_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user),
):
    skill = await get_skill_full(db, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillFullOut.model_validate(skill)


@router.post("/skills", response_model=SkillFullOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    skill = Skill(
        name=body.name,
        description=body.description,
        version=body.version,
        category=body.category,
        catalog_summary=body.catalog_summary,
        icon=body.icon,
        system_prompt=body.system_prompt,
        tool_configuration=body.tool_configuration,
        example_prompts=body.example_prompts,
        parameters=body.parameters,
        source_type="custom",
        created_by=user.id,
    )
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    return SkillFullOut.model_validate(skill)


@router.put("/skills/{skill_id}", response_model=SkillFullOut)
async def update_skill(
    skill_id: uuid.UUID,
    body: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    skill = await get_skill_full(db, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)
    await db.flush()
    await db.refresh(skill)
    return SkillFullOut.model_validate(skill)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    skill = await get_skill_full(db, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    await db.delete(skill)
    await db.flush()


@router.post("/skills/{skill_id}/activate")
async def activate_skill_endpoint(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    skill = await get_skill_full(db, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    system_prompt, tools = activate_skill(skill)
    return {
        "skill_id": str(skill_id),
        "system_prompt": system_prompt,
        "tools": tools,
        "name": skill.name,
    }

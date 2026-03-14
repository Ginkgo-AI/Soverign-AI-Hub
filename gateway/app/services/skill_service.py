"""Skill service — catalog, activation, and default skill seeding."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill

logger = logging.getLogger(__name__)


# -- Default skills -----------------------------------------------------------

_DEFAULT_SKILLS: list[dict[str, Any]] = [
    {
        "name": "Research Assistant",
        "description": "Deep research with source citation and synthesis",
        "category": "research",
        "catalog_summary": "Search documents, synthesize findings, cite sources",
        "icon": "search",
        "system_prompt": (
            "You are a thorough research assistant. Use RAG search to find relevant documents, "
            "synthesize findings across multiple sources, and always cite your sources. "
            "Present research in a structured format with key findings, supporting evidence, "
            "and identified gaps."
        ),
        "tool_configuration": ["rag_search", "file_read", "calculator"],
        "example_prompts": [
            "Research the impact of AI on healthcare delivery",
            "Find all documents related to budget planning for Q3",
            "Compare the two policy proposals on cybersecurity",
        ],
    },
    {
        "name": "Data Analyst",
        "description": "SQL queries, Python analysis, and data visualization",
        "category": "analysis",
        "catalog_summary": "Query databases, analyze data, generate insights",
        "icon": "bar-chart",
        "system_prompt": (
            "You are an expert data analyst. Use SQL queries to explore the database, "
            "Python for complex analysis and transformations, and the calculator for quick math. "
            "Always present findings with numbers, percentages, and clear summaries. "
            "Create visualizations when helpful."
        ),
        "tool_configuration": ["sql_query", "python_exec", "calculator", "rag_search"],
        "example_prompts": [
            "Show me usage statistics for the last 30 days",
            "Analyze the distribution of document types in our collections",
            "Calculate the average response time by model",
        ],
    },
    {
        "name": "Code Review",
        "description": "Analyze code for bugs, security issues, and best practices",
        "category": "coding",
        "catalog_summary": "Review code quality, find bugs, suggest improvements",
        "icon": "code",
        "system_prompt": (
            "You are a senior code reviewer. Analyze code for bugs, security vulnerabilities, "
            "performance issues, and adherence to best practices. Provide specific, actionable "
            "feedback with code examples. Prioritize issues by severity."
        ),
        "tool_configuration": ["code_analyze", "code_explain", "file_read", "python_exec"],
        "example_prompts": [
            "Review this Python function for security issues",
            "Analyze the error handling in this module",
            "Suggest performance improvements for this algorithm",
        ],
    },
    {
        "name": "Report Writer",
        "description": "Generate structured reports from data and documents",
        "category": "writing",
        "catalog_summary": "Draft reports, memos, and structured documents",
        "icon": "file-text",
        "system_prompt": (
            "You are a professional report writer. Generate clear, well-structured reports "
            "with executive summaries, detailed findings, and recommendations. Use data from "
            "searches and queries to support your points. Adapt tone to the audience."
        ),
        "tool_configuration": ["rag_search", "sql_query", "calculator", "file_write"],
        "example_prompts": [
            "Write a weekly status report based on recent activities",
            "Draft a technical assessment of our AI infrastructure",
            "Create an executive summary of the Q2 findings",
        ],
    },
    {
        "name": "System Admin",
        "description": "System diagnostics, monitoring, and troubleshooting",
        "category": "operations",
        "catalog_summary": "Monitor systems, diagnose issues, run commands",
        "icon": "terminal",
        "system_prompt": (
            "You are a system administrator assistant. Help diagnose system issues, "
            "run diagnostic commands, check logs, and suggest fixes. Always explain "
            "what commands do before running them. Prioritize safety — never run "
            "destructive commands without explicit confirmation."
        ),
        "tool_configuration": ["bash_exec", "python_exec", "file_read", "http_request"],
        "example_prompts": [
            "Check disk usage and memory status",
            "Look at recent error logs",
            "Test connectivity to the vector database",
        ],
    },
]


async def get_skill_catalog(db: AsyncSession) -> list[Skill]:
    """Return lightweight catalog of all enabled skills."""
    result = await db.execute(
        select(Skill).where(Skill.enabled == True).order_by(Skill.category, Skill.name)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_skill_full(db: AsyncSession, skill_id: uuid.UUID) -> Skill | None:
    """Load full skill definition."""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalar_one_or_none()


def activate_skill(skill: Skill) -> tuple[str, list[str]]:
    """Return augmented system prompt and tool list for an activated skill."""
    return skill.system_prompt, skill.tool_configuration


async def seed_default_skills(db: AsyncSession) -> int:
    """Insert default skills if the table is empty."""
    count_result = await db.execute(select(func.count(Skill.id)))
    if count_result.scalar_one() > 0:
        return 0

    for defn in _DEFAULT_SKILLS:
        skill = Skill(
            name=defn["name"],
            description=defn["description"],
            category=defn["category"],
            catalog_summary=defn["catalog_summary"],
            icon=defn["icon"],
            system_prompt=defn["system_prompt"],
            tool_configuration=defn["tool_configuration"],
            example_prompts=defn["example_prompts"],
            source_type="builtin",
        )
        db.add(skill)

    await db.flush()
    logger.info("Seeded %d default skills", len(_DEFAULT_SKILLS))
    return len(_DEFAULT_SKILLS)

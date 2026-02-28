"""Data classification service for Phase 6.

Enforces classification-level access rules and prevents cross-classification
data mixing.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.schemas.security import (
    CLASSIFICATION_BANNERS,
    CLASSIFICATION_HIERARCHY,
    ClassificationLevel,
)


def parse_level(level: str) -> ClassificationLevel:
    """Parse a string into a ``ClassificationLevel`` enum value."""
    try:
        return ClassificationLevel(level.upper())
    except ValueError:
        return ClassificationLevel.UNCLASSIFIED


def level_rank(level: ClassificationLevel | str) -> int:
    """Return the numeric rank of a classification level."""
    if isinstance(level, str):
        level = parse_level(level)
    return CLASSIFICATION_HIERARCHY.get(level, 0)


def check_classification_access(
    user_classification_level: str,
    resource_classification: str,
) -> bool:
    """Return ``True`` if the user's clearance meets or exceeds the resource level."""
    return level_rank(user_classification_level) >= level_rank(resource_classification)


def enforce_classification_access(
    user_classification_level: str,
    resource_classification: str,
) -> None:
    """Raise 403 if the user's clearance is insufficient."""
    if not check_classification_access(user_classification_level, resource_classification):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Insufficient classification clearance. "
                f"Resource requires '{resource_classification}'; "
                f"your clearance is '{user_classification_level}'."
            ),
        )


def can_mix_classifications(
    source_level: str,
    target_level: str,
) -> bool:
    """Return ``True`` if data from *source_level* may be used in *target_level* context.

    Higher-classified data must NOT flow to a lower-classification context.
    """
    return level_rank(source_level) <= level_rank(target_level)


def enforce_no_downgrade(
    source_level: str,
    target_level: str,
) -> None:
    """Raise 403 if mixing would downgrade classification."""
    if not can_mix_classifications(source_level, target_level):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Classification downgrade denied. "
                f"Cannot use '{source_level}' data in a '{target_level}' context."
            ),
        )


def get_classification_banner(level: str) -> dict[str, str]:
    """Return banner colour/label/warning for the given classification level."""
    parsed = parse_level(level)
    return CLASSIFICATION_BANNERS.get(
        parsed,
        CLASSIFICATION_BANNERS[ClassificationLevel.UNCLASSIFIED],
    )


def effective_classification(*levels: str) -> str:
    """Return the highest classification among the given levels."""
    if not levels:
        return ClassificationLevel.UNCLASSIFIED.value
    best = max(levels, key=lambda l: level_rank(l))
    return parse_level(best).value

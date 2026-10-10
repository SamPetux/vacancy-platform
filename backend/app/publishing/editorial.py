"""Editorial grade (internal) and public marker selection via CreativeContext."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.content.creative_context import CreativeContext, build_creative_context
from app.content.markers import MARKERS, MarkerKey
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.availability import FieldAvailability
from app.publishing.grades import assign_grade
from app.publishing.models import EditorialRating

__all__ = ["GradeResult", "assign_grade", "build_editorial", "explanation_signals"]


@dataclass(frozen=True)
class GradeResult:
    grade: str
    label: str
    reason: str


def build_editorial(
    vacancy: Vacancy,
    availability: FieldAvailability,
    score: VacancyScore | None,
    *,
    variant: int = 0,
    creative: CreativeContext | None = None,
    salary_percentile: float | None = None,
    salary_sample: int = 0,
    role_frequency: float | None = None,
) -> EditorialRating | None:
    """Public editorial uses marker label; grade kept for admin/analytics only."""
    vqs = vacancy.quality_score
    feed = vacancy.feed_score
    if vqs is None and feed is None:
        return None

    grade = assign_grade(vqs=vqs, feed_score=feed)
    ais: float | None = None
    if score is not None and score.audience_interest is not None:
        ais = float(score.audience_interest)
    else:
        raw_ais = getattr(vacancy, "audience_interest_score", None)
        if raw_ais is not None:
            ais = float(raw_ais)
    ctx = creative or build_creative_context(
        vacancy,
        score,
        availability=availability,
        salary_percentile=salary_percentile,
        salary_sample=salary_sample,
        role_frequency=role_frequency,
        audience_interest=ais,
    )
    # variant rotates secondary preference among near-tied markers via layout only
    _ = variant
    try:
        label = MARKERS[MarkerKey(ctx.creative_type)].label
    except ValueError:
        label = ctx.primary_signal.upper()

    return EditorialRating(
        grade=grade,
        label=label,
        reason=ctx.editorial_reason,
        creative_type=ctx.creative_type,
        visual_family=ctx.visual_family,
        layout_variant=ctx.layout_variant,
        confidence=ctx.confidence,
        show_grade_publicly=False,
    )


def explanation_signals(score: VacancyScore | None) -> list[str]:
    """Debug helper for tests / admin."""
    detail: dict[str, Any] = {}
    if score and isinstance(score.components_detail, dict):
        detail = score.components_detail
    return list(detail.keys())

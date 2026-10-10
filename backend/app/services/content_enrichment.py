"""Enrich vacancy publication with AIS, CreativeContext, and visual choice."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.audience_interest import compute_audience_interest
from app.content.cohort import experience_band, role_frequency, salary_percentile
from app.content.creative_context import CreativeContext, build_creative_context
from app.content.markers import MARKERS, MarkerKey, marker_label
from app.content.visual.composer import ComposeRequest, compose_card
from app.content.visual.rotation import RecentVisual, select_visual
from app.models.content_item import ContentItem
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.availability import assess_availability

_RENDER_DIR = Path(__file__).resolve().parents[3] / "assets" / "generated"


async def enrich_vacancy_scores(
    session: AsyncSession,
    vacancy: Vacancy,
    score: VacancyScore,
) -> float:
    """Compute AIS, persist on VacancyScore; return total. Does not change VQS/Feed."""
    mid = _salary_mid(vacancy)
    pct: float | None = None
    sample = 0
    if mid is not None:
        pct, sample = await salary_percentile(
            session,
            city_id=vacancy.city_id,
            category=vacancy.category,
            salary=mid,
            experience_band=experience_band(vacancy.experience_required),
        )
    freq, _ = await role_frequency(
        session,
        city_id=vacancy.city_id,
        professional_role=vacancy.professional_role,
        title=vacancy.title,
    )
    avail = assess_availability(vacancy)
    ais = compute_audience_interest(
        vacancy,
        score,
        availability=avail,
        role_frequency=freq,
        salary_percentile=pct,
    )
    score.audience_interest = ais.total
    detail = dict(score.components_detail or {})
    detail["audience_interest"] = ais.explanation
    detail["cohort"] = {
        "salary_percentile": pct,
        "salary_sample": sample,
        "role_frequency": freq,
    }
    score.components_detail = detail
    vacancy.audience_interest_score = ais.total
    return ais.total


async def build_context_for_vacancy(
    session: AsyncSession,
    vacancy: Vacancy,
    score: VacancyScore | None,
    *,
    city_name: str,
) -> tuple[CreativeContext, dict[str, Any], Path | None]:
    """Build CreativeContext + visual dict + optional rendered PNG path."""
    avail = assess_availability(vacancy)
    mid = _salary_mid(vacancy)
    pct: float | None = None
    sample = 0
    if mid is not None:
        pct, sample = await salary_percentile(
            session,
            city_id=vacancy.city_id,
            category=vacancy.category,
            salary=mid,
            experience_band=experience_band(vacancy.experience_required),
        )
    freq, _ = await role_frequency(
        session,
        city_id=vacancy.city_id,
        professional_role=vacancy.professional_role,
        title=vacancy.title,
    )
    recent = await _recent_visuals(session, vacancy.city_id)
    ais_total: float | None = None
    if score is not None and score.audience_interest is not None:
        ais_total = float(score.audience_interest)
    elif vacancy.audience_interest_score is not None:
        ais_total = float(vacancy.audience_interest_score)

    ctx = build_creative_context(
        vacancy,
        score,
        availability=avail,
        salary_percentile=pct,
        salary_sample=sample,
        role_frequency=freq,
        audience_interest=ais_total,
        recent_markers=[r.marker_key for r in recent],
        recent_families=[r.family for r in recent],
    )

    data_point = None
    if avail.schedule_label in {"2/2", "3/3", "5/2"}:
        data_point = avail.schedule_label
    elif avail.experience_label == "без опыта":
        data_point = "0 ЛЕТ ОПЫТА"

    choice = select_visual(
        marker_key=ctx.creative_type,
        category=ctx.category,
        preferred_family=ctx.visual_family,
        preferred_layout=ctx.layout_variant,
        recent=recent,
        data_point_available=data_point is not None,
    )
    ctx.visual_family = choice.family.value
    ctx.layout_variant = choice.layout_variant

    visual = {
        "family": choice.family.value,
        "layout_variant": choice.layout_variant,
        "accent": choice.accent,
        "marker": choice.marker_key,
        "data_point": data_point,
    }

    label = marker_label(ctx.creative_type)
    out_path = _RENDER_DIR / f"{vacancy.id}_{choice.family.value}_{choice.layout_variant}.png"
    compose_card(
        ComposeRequest(
            marker_label=label,
            visual_family=choice.family.value,
            layout_variant=choice.layout_variant,
            category=ctx.category,
            secondary_signal=ctx.secondary_signal,
            data_point=data_point,
            city_label=city_name,
            accent=choice.accent,
        ),
        output_path=out_path,
    )
    visual["image_path"] = str(out_path)
    return ctx, visual, out_path


async def _recent_visuals(
    session: AsyncSession,
    city_id: UUID,
    limit: int = 8,
) -> list[RecentVisual]:
    stmt = (
        select(ContentItem)
        .where(
            ContentItem.city_id == city_id,
            ContentItem.status == "published",
        )
        .order_by(ContentItem.published_at.desc().nulls_last())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    out: list[RecentVisual] = []
    for row in reversed(rows):
        visual = row.visual or {}
        ctx = row.creative_context or {}
        out.append(
            RecentVisual(
                family=str(visual.get("family") or ""),
                layout_variant=str(visual.get("layout_variant") or ""),
                marker_key=str(visual.get("marker") or ctx.get("creative_type") or ""),
                category=str(ctx.get("category") or ""),
                accent=str(visual.get("accent") or ""),
            )
        )
    return out


def _salary_mid(vacancy: Vacancy) -> float | None:
    if vacancy.salary_from and vacancy.salary_to:
        return (float(vacancy.salary_from) + float(vacancy.salary_to)) / 2.0
    if vacancy.salary_from:
        return float(vacancy.salary_from)
    if vacancy.salary_to:
        return float(vacancy.salary_to)
    return None


def creative_to_editorial_public(ctx: CreativeContext) -> dict[str, str]:
    """Map CreativeContext to public editorial fields (no letter grade)."""
    try:
        label = MARKERS[MarkerKey(ctx.creative_type)].label
    except ValueError:
        label = ctx.primary_signal.upper()
    return {
        "grade": "",  # intentionally blank publicly
        "label": label,
        "reason": ctx.editorial_reason,
        "internal_grade": ctx.internal_grade or "",
        "creative_type": ctx.creative_type,
    }

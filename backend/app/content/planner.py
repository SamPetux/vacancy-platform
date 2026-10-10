"""ContentPlanner — soft mix of content types within existing daily limits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.collections import (
    CollectionTheme,
    generate_collection,
    render_collection_text,
)
from app.core.config import Settings
from app.models.city import City
from app.models.content_item import ContentItem
from app.models.enums import VacancyStatus
from app.models.vacancy import Vacancy

# Soft targets — quality over exact percentages.
DEFAULT_MIX: dict[str, float] = {
    "VACANCY": 0.65,
    "COLLECTION": 0.15,
    "SALARY_INSIGHT": 0.10,
    "RARE_ROLES": 0.05,
    "CAREER_PATH": 0.05,
}


@dataclass(frozen=True, slots=True)
class PlanResult:
    created: list[UUID]
    skipped: list[str]
    mix_snapshot: dict[str, int]


async def plan_city_day(
    session: AsyncSession,
    city: City,
    settings: Settings,
    *,
    collections_enabled: bool | None = None,
) -> PlanResult:
    """Allocate content slots for today without exceeding city daily target."""
    enabled = (
        settings.content_engine_collections_enabled
        if collections_enabled is None
        else collections_enabled
    )
    target = max(1, int(city.target_items_per_day or 20))
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    existing_counts = await _type_counts(session, city.id, since)
    total_existing = sum(existing_counts.values())
    remaining = max(0, target - total_existing)
    if remaining == 0:
        return PlanResult(
            created=[],
            skipped=["daily_target_reached"],
            mix_snapshot=existing_counts,
        )

    created: list[UUID] = []
    skipped: list[str] = []

    # Always prefer syncing READY vacancies into ContentItems first.
    vacancy_slots = _desired_count("VACANCY", remaining, existing_counts, target)
    synced = await _sync_ready_vacancies(session, city, limit=vacancy_slots)
    created.extend(synced)
    remaining -= len(synced)

    if enabled and remaining > 0:
        for content_type, theme in (
            ("COLLECTION", "weekly_highlights"),
            ("SALARY_INSIGHT", "salary_floor"),
            ("RARE_ROLES", "rare_roles"),
            ("CAREER_PATH", "career_path"),
        ):
            want = _desired_count(content_type, remaining, existing_counts, target)
            if want <= 0:
                continue
            item_id = await _try_collection(
                session,
                city,
                content_type=content_type,
                theme=theme,  # type: ignore[arg-type]
            )
            if item_id is None:
                skipped.append(f"insufficient_data:{content_type}")
            else:
                created.append(item_id)
                remaining -= 1
                existing_counts[content_type] = existing_counts.get(content_type, 0) + 1

    await session.flush()
    return PlanResult(
        created=created,
        skipped=skipped,
        mix_snapshot=await _type_counts(session, city.id, since),
    )


def _desired_count(
    content_type: str,
    remaining: int,
    existing: dict[str, int],
    target: int,
) -> int:
    if remaining <= 0:
        return 0
    ratio = DEFAULT_MIX.get(content_type, 0.0)
    ideal = int(round(target * ratio))
    have = existing.get(content_type, 0)
    need = max(0, ideal - have)
    return min(need, remaining)


async def _type_counts(
    session: AsyncSession,
    city_id: UUID,
    since: datetime,
) -> dict[str, int]:
    stmt = (
        select(ContentItem.content_type, func.count())
        .where(
            ContentItem.city_id == city_id,
            ContentItem.created_at >= since,
            ContentItem.status.in_(("draft", "planned", "ready", "published")),
        )
        .group_by(ContentItem.content_type)
    )
    rows = (await session.execute(stmt)).all()
    return {str(t): int(c) for t, c in rows}


async def _sync_ready_vacancies(
    session: AsyncSession,
    city: City,
    *,
    limit: int,
) -> list[UUID]:
    if limit <= 0:
        return []
    stmt: Select[tuple[Vacancy]] = (
        select(Vacancy)
        .where(
            Vacancy.city_id == city.id,
            Vacancy.moderation_status == VacancyStatus.READY_FOR_PUBLICATION,
        )
        .order_by(
            Vacancy.ranked_position.asc().nulls_last(),
            Vacancy.feed_score.desc().nulls_last(),
        )
        .limit(limit * 2)
    )
    vacancies = list((await session.execute(stmt)).scalars().all())
    created: list[UUID] = []
    for v in vacancies:
        if len(created) >= limit:
            break
        exists = await session.scalar(
            select(ContentItem.id).where(
                ContentItem.vacancy_id == v.id,
                ContentItem.content_type == "VACANCY",
                ContentItem.status.in_(("draft", "planned", "ready", "published")),
            )
        )
        if exists:
            continue
        row = ContentItem(
            city_id=city.id,
            content_type="VACANCY",
            status="ready",
            vacancy_id=v.id,
            payload={},
            ranked_position=v.ranked_position,
            audience_interest_score=None,
        )
        session.add(row)
        await session.flush()
        created.append(row.id)
    return created


async def _try_collection(
    session: AsyncSession,
    city: City,
    *,
    content_type: str,
    theme: CollectionTheme,
) -> UUID | None:
    prior = list(
        (
            await session.execute(
                select(ContentItem).where(
                    ContentItem.city_id == city.id,
                    ContentItem.content_type == content_type,
                    ContentItem.created_at >= datetime.now(UTC) - timedelta(days=14),
                )
            )
        ).scalars().all()
    )
    fps = {
        str((row.payload or {}).get("fingerprint"))
        for row in prior
        if (row.payload or {}).get("fingerprint")
    }

    kwargs: dict[str, Any] = {
        "city_id": city.id,
        "city_name": city.name,
        "theme": theme,
        "existing_fingerprints": {f for f in fps if f},
    }
    if theme == "salary_floor":
        kwargs["salary_floor"] = 100_000.0
        kwargs["period_days"] = 30
        kwargs["min_items"] = 3

    draft = await generate_collection(session, **kwargs)
    if draft is None:
        return None

    text = render_collection_text(draft)
    row = ContentItem(
        city_id=city.id,
        content_type=content_type,
        status="draft",  # preview first; not auto-published until enabled
        vacancy_id=None,
        payload={
            "theme": draft.theme,
            "title": draft.title,
            "vacancy_ids": [str(i) for i in draft.vacancy_ids],
            "items": draft.items,
            "disclaimer": draft.disclaimer,
            "fingerprint": draft.fingerprint,
            "sample_size": draft.sample_size,
            "period_days": draft.period_days,
        },
        rendered_text=text,
        creative_context={
            "creative_type": "COLLECTION",
            "primary_signal": draft.title,
            "visual_family": "RADAR_TYPOGRAPHY",
            "layout_variant": "typo_01",
            "editorial_reason": draft.intro,
            "confidence": 0.7,
            "category": "collection",
        },
        visual={
            "family": "RADAR_TYPOGRAPHY",
            "layout_variant": "typo_01",
            "marker": "WORTH_NOTICING",
        },
    )
    session.add(row)
    await session.flush()
    return row.id

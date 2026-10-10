"""City cohort stats for salary percentiles and role rarity (own DB sample)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VacancyStatus
from app.models.vacancy import Vacancy

_ACTIVE = (
    VacancyStatus.SCORED,
    VacancyStatus.READY_FOR_PUBLICATION,
    VacancyStatus.APPROVED_FOR_PUBLICATION,
    VacancyStatus.PUBLISHED,
    VacancyStatus.WAITING_MODERATION,
)


def _salary_mid(vacancy: Vacancy) -> float | None:
    if vacancy.salary_from and vacancy.salary_to:
        return (float(vacancy.salary_from) + float(vacancy.salary_to)) / 2.0
    if vacancy.salary_from:
        return float(vacancy.salary_from)
    if vacancy.salary_to:
        return float(vacancy.salary_to)
    return None


async def salary_percentile(
    session: AsyncSession,
    *,
    city_id: UUID,
    category: str | None,
    salary: float,
    experience_band: str | None = None,
    days: int = 90,
    min_sample: int = 15,
) -> tuple[float | None, int]:
    """Return (percentile 0..100, sample_size) vs city+category cohort.

    Returns (None, n) when sample < min_sample — caller must not claim ABOVE_MARKET.
    """
    since = datetime.now(UTC) - timedelta(days=days)
    cat = (category or "other").lower()
    stmt: Select[tuple[Vacancy]] = select(Vacancy).where(
        Vacancy.city_id == city_id,
        Vacancy.created_at >= since,
        Vacancy.moderation_status.in_(_ACTIVE),
        Vacancy.category == cat,
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    mids: list[float] = []
    for v in rows:
        mid = _salary_mid(v)
        if mid is None:
            continue
        if experience_band:
            exp = (v.experience_required or "").lower()
            if experience_band == "junior" and not (
                "без опыта" in exp or "не имеет значения" in exp or "1" in exp
            ):
                continue
            if experience_band == "senior" and not any(x in exp for x in ("2", "3", "4", "5", "6")):
                continue
        mids.append(mid)
    n = len(mids)
    if n < min_sample:
        return None, n
    below = sum(1 for m in mids if m <= salary)
    pct = round(100.0 * below / n, 2)
    return pct, n


async def role_frequency(
    session: AsyncSession,
    *,
    city_id: UUID,
    professional_role: str | None,
    title: str | None,
    days: int = 90,
) -> tuple[float | None, int]:
    """Share of vacancies with same role/title cluster in city (0..1)."""
    since = datetime.now(UTC) - timedelta(days=days)
    total_stmt = select(func.count()).select_from(Vacancy).where(
        Vacancy.city_id == city_id,
        Vacancy.created_at >= since,
        Vacancy.moderation_status.in_(_ACTIVE),
    )
    total = int(await session.scalar(total_stmt) or 0)
    if total == 0:
        return None, 0

    key = (professional_role or title or "").strip().lower()
    if len(key) < 3:
        return None, total

    # Cluster by professional_role when present, else title prefix.
    if professional_role and professional_role.strip():
        match_stmt = select(func.count()).select_from(Vacancy).where(
            Vacancy.city_id == city_id,
            Vacancy.created_at >= since,
            Vacancy.moderation_status.in_(_ACTIVE),
            func.lower(Vacancy.professional_role) == professional_role.strip().lower(),
        )
    else:
        prefix = key[:24]
        match_stmt = select(func.count()).select_from(Vacancy).where(
            Vacancy.city_id == city_id,
            Vacancy.created_at >= since,
            Vacancy.moderation_status.in_(_ACTIVE),
            func.lower(Vacancy.title).like(f"{prefix}%"),
        )
    matched = int(await session.scalar(match_stmt) or 0)
    return round(matched / total, 4), total


def experience_band(experience_required: str | None) -> str | None:
    if not experience_required:
        return None
    lowered = experience_required.lower()
    if "без опыта" in lowered or "не имеет значения" in lowered:
        return "junior"
    if any(x in lowered for x in ("2", "3", "4", "5", "6")):
        return "senior"
    if "1" in lowered:
        return "junior"
    return None

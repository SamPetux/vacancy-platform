"""CollectionGenerator — thematic vacancy roundups from the existing DB."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VacancyStatus
from app.models.vacancy import Vacancy
from app.publishing.salary import format_salary_line

CollectionTheme = Literal[
    "weekly_highlights",
    "no_experience",
    "flex_format",
    "category",
    "salary_floor",
    "rare_roles",
    "career_path",
]

_PUBLISHABLE = (
    VacancyStatus.SCORED,
    VacancyStatus.READY_FOR_PUBLICATION,
    VacancyStatus.APPROVED_FOR_PUBLICATION,
    VacancyStatus.PUBLISHED,
)


@dataclass(frozen=True, slots=True)
class CollectionDraft:
    theme: str
    title: str
    intro: str
    vacancy_ids: list[UUID]
    items: list[dict[str, Any]]
    disclaimer: str | None
    fingerprint: str
    sample_size: int
    period_days: int


async def generate_collection(
    session: AsyncSession,
    *,
    city_id: UUID,
    city_name: str,
    theme: CollectionTheme,
    category: str | None = None,
    salary_floor: float | None = None,
    min_vqs: float = 50.0,
    min_feed: float = 40.0,
    min_items: int = 3,
    max_items: int = 7,
    period_days: int = 7,
    existing_fingerprints: set[str] | None = None,
) -> CollectionDraft | None:
    """Build a collection from real active vacancies. Returns None if insufficient data."""
    since = datetime.now(UTC) - timedelta(days=period_days)
    stmt: Select[tuple[Vacancy]] = (
        select(Vacancy)
        .where(
            Vacancy.city_id == city_id,
            Vacancy.created_at >= since,
            Vacancy.moderation_status.in_(_PUBLISHABLE),
            Vacancy.quality_score >= min_vqs,
            Vacancy.feed_score >= min_feed,
        )
        .order_by(Vacancy.feed_score.desc().nulls_last(), Vacancy.quality_score.desc().nulls_last())
        .limit(80)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    filtered = _filter(rows, theme=theme, category=category, salary_floor=salary_floor)
    filtered = _diversify(filtered, max_items=max_items)
    if len(filtered) < min_items:
        return None

    ids = [v.id for v in filtered]
    fp = _fingerprint(theme, category, salary_floor, ids)
    if existing_fingerprints and fp in existing_fingerprints:
        return None

    items = [_item_row(v, i + 1) for i, v in enumerate(filtered)]
    title, intro, disclaimer = _copy(
        theme=theme,
        city_name=city_name,
        count=len(filtered),
        category=category,
        salary_floor=salary_floor,
        period_days=period_days,
        sample_size=len(rows),
    )
    return CollectionDraft(
        theme=theme,
        title=title,
        intro=intro,
        vacancy_ids=ids,
        items=items,
        disclaimer=disclaimer,
        fingerprint=fp,
        sample_size=len(rows),
        period_days=period_days,
    )


def render_collection_text(draft: CollectionDraft) -> str:
    lines = [draft.title, "", draft.intro, ""]
    for row in draft.items:
        lines.append(f"{row['index']:02d} / {row['title']}")
        if row.get("salary"):
            lines.append(row["salary"])
        if row.get("company"):
            lines.append(row["company"])
        lines.append("")
    if draft.disclaimer:
        lines.append(draft.disclaimer)
        lines.append("")
    lines.append("Открыть вакансии —")
    for row in draft.items:
        if row.get("source_url"):
            lines.append(row["source_url"])
    return "\n".join(lines).strip() + "\n"


def _filter(
    rows: list[Vacancy],
    *,
    theme: str,
    category: str | None,
    salary_floor: float | None,
) -> list[Vacancy]:
    out: list[Vacancy] = []
    for v in rows:
        cat = (v.category or "other").lower()
        exp = (v.experience_required or "").lower()
        remote = (v.remote_type or "").lower()
        sched = (v.schedule or "").lower()
        mid = _mid_salary(v)

        if theme == "no_experience":
            if "без опыта" not in exp and "не имеет значения" not in exp:
                continue
        elif theme == "flex_format":
            if not (
                remote in {"remote", "hybrid", "удалённо", "удаленно", "гибрид"}
                or "удал" in sched
                or "гибрид" in sched
                or "гибк" in sched
            ):
                continue
        elif theme == "category":
            if not category or cat != category.lower():
                continue
        elif theme == "salary_floor":
            if salary_floor is None or mid is None or mid < salary_floor:
                continue
        elif theme == "rare_roles":
            if cat in {"mass", "sales", "other", "hospitality"}:
                continue
        elif theme == "career_path":
            if cat not in {"it", "engineering", "medicine", "marketing", "education"}:
                continue
            if "без опыта" not in exp and float(v.quality_score or 0) < 60:
                continue
        # weekly_highlights: keep ranked list
        out.append(v)
    return out


def _diversify(rows: list[Vacancy], *, max_items: int) -> list[Vacancy]:
    picked: list[Vacancy] = []
    cats: dict[str, int] = {}
    companies: dict[str, int] = {}
    for v in rows:
        cat = (v.category or "other").lower()
        company = (v.company_name or "").lower().strip()
        if cats.get(cat, 0) >= 2:
            continue
        if company and companies.get(company, 0) >= 1:
            continue
        picked.append(v)
        cats[cat] = cats.get(cat, 0) + 1
        if company:
            companies[company] = companies.get(company, 0) + 1
        if len(picked) >= max_items:
            break
    return picked


def _item_row(v: Vacancy, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "vacancy_id": str(v.id),
        "title": (v.title or "Вакансия").strip(),
        "company": (v.company_name or "").strip() or None,
        "salary": format_salary_line(v.salary_from, v.salary_to, currency=v.salary_currency),
        "source_url": v.source_url,
        "category": v.category,
    }


def _mid_salary(v: Vacancy) -> float | None:
    if v.salary_from and v.salary_to:
        return (float(v.salary_from) + float(v.salary_to)) / 2.0
    if v.salary_from:
        return float(v.salary_from)
    if v.salary_to:
        return float(v.salary_to)
    return None


def _fingerprint(
    theme: str,
    category: str | None,
    salary_floor: float | None,
    ids: list[UUID],
) -> str:
    raw = f"{theme}|{category or ''}|{salary_floor or ''}|{','.join(sorted(str(i) for i in ids))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _copy(
    *,
    theme: str,
    city_name: str,
    count: int,
    category: str | None,
    salary_floor: float | None,
    period_days: int,
    sample_size: int,
) -> tuple[str, str, str | None]:
    if theme == "weekly_highlights":
        title = f"{count} интересных вакансий недели в {city_name}"
        intro = (
            "За последние дни нашли несколько предложений, "
            "которые стоит заметить — от старта до сильных ролей."
        )
        return title, intro, None
    if theme == "no_experience":
        title = f"{count} вакансий без опыта, которые стоит рассмотреть"
        intro = f"Подборка позиций в {city_name}, где работодатель явно готов к новичкам."
        return title, intro, None
    if theme == "flex_format":
        title = f"Работа с гибким графиком: подборка в {city_name}"
        intro = f"{count} предложений с удалёнкой, гибридом или гибким форматом."
        return title, intro, None
    if theme == "category":
        label = (category or "сфера").capitalize()
        title = f"{count} предложений для сферы «{label}»"
        intro = f"Тематическая подборка по {city_name}."
        return title, intro, None
    if theme == "salary_floor":
        floor = int(salary_floor or 0)
        title = f"Где в {city_name} предлагают от {floor // 1000} тысяч?"
        intro = f"{count} вакансий с указанной вилкой от {floor:,} ₽.".replace(",", " ")
        disclaimer = (
            f"По нашей выборке за {period_days} дн., N={sample_size} вакансий "
            f"с зарплатой в базе. Это не статистика всего рынка."
        )
        return title, intro, disclaimer
    if theme == "rare_roles":
        title = f"Необычная работа в {city_name}: какие вакансии мы нашли"
        intro = f"{count} менее типичных ролей из текущей базы."
        return title, intro, None
    if theme == "career_path":
        title = f"{count} вакансий для тех, кто хочет сделать карьерный шаг"
        intro = f"Позиции с полезным опытом и понятными требованиями в {city_name}."
        return title, intro, None
    title = f"{count} вакансий в {city_name}, которые стоит заметить"
    intro = "Подборка из актуальных предложений базы."
    return title, intro, None

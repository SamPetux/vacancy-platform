"""Re-parse and re-score existing vacancies, then rebuild the feed queue."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import City, RawItem, Vacancy, VacancyScore, VacancyStatus
from app.parsing.extract import parse_vacancy_text
from app.parsing.location import OUT_OF_CITY_FLAG, build_location_policy, evaluate_work_location
from app.scoring.feed_score import compute_feed_score
from app.scoring.vqs import compute_vqs
from app.services.collection import CollectionPipeline, _component_value

logger = logging.getLogger(__name__)


async def rescore_city(
    session: AsyncSession,
    city_slug: str,
    settings: Settings | None = None,
) -> dict[str, int]:
    settings = settings or get_settings()
    city = (
        await session.execute(select(City).where(City.slug == city_slug))
    ).scalar_one()

    result = await session.execute(
        select(Vacancy).where(
            Vacancy.city_id == city.id,
            Vacancy.moderation_status.in_(
                [
                    VacancyStatus.SCORED,
                    VacancyStatus.READY_FOR_PUBLICATION,
                    VacancyStatus.REJECTED_AUTOMATICALLY,
                    VacancyStatus.PARSED,
                ]
            ),
        )
    )
    vacancies = list(result.scalars().all())
    category_counts: dict[str, int] = {}
    company_counts: dict[str, int] = {}
    updated = 0
    out_of_city = 0
    location_policy = build_location_policy(
        city_name=city.name,
        region_name=city.region,
        aliases=[str(a) for a in (city.location_aliases or [])],
        allow_remote=bool(city.allow_remote),
    )

    for vac in vacancies:
        structured = await _load_structured(session, vac.raw_item_id)
        parsed = parse_vacancy_text(vac.raw_text, structured=structured)
        vac.title = parsed.title or vac.title
        vac.company_name = parsed.company_name or vac.company_name
        vac.category = parsed.category
        vac.professional_role = parsed.professional_role
        vac.salary_from = float(parsed.salary_from) if parsed.salary_from else vac.salary_from
        vac.salary_to = float(parsed.salary_to) if parsed.salary_to else vac.salary_to
        vac.schedule = parsed.schedule or vac.schedule
        vac.hours_per_day = parsed.hours_per_day or vac.hours_per_day
        # Recompute remote from current text; do not keep sticky false positives.
        vac.remote_type = parsed.remote_type
        vac.experience_required = parsed.experience_required or vac.experience_required
        vac.requirements = parsed.requirements or vac.requirements
        vac.duties = parsed.duties or vac.duties
        vac.contact = parsed.contact or vac.contact
        vac.contact_type = parsed.contact_type or vac.contact_type
        vac.address = parsed.address or vac.address
        vac.clean_text = parsed.clean_text

        location = evaluate_work_location(
            text=vac.raw_text,
            policy=location_policy,
            address=vac.address,
            remote_type=parsed.remote_type,
            schedule=parsed.schedule or vac.schedule,
            structured=structured,
        )
        if location.is_remote:
            vac.remote_type = "remote"
        elif location.work_location:
            vac.remote_type = None
        if location.work_location and (
            not vac.address or vac.address.strip().lower() in {"не имеет значения"}
        ):
            vac.address = location.work_location[:512]

        if not location.allowed:
            vac.moderation_status = VacancyStatus.REJECTED_AUTOMATICALLY
            vac.flags = [location.flag or OUT_OF_CITY_FLAG]
            vac.score_explanation = {
                "location": {
                    "reason": location.reason,
                    "work_location": location.work_location,
                    "is_remote": location.is_remote,
                }
            }
            vac.quality_score = None
            vac.feed_score = None
            vac.ranked_position = None
            out_of_city += 1
            updated += 1
            continue

        vqs = compute_vqs(parsed, vac.raw_text)
        feed = compute_feed_score(
            vqs=vqs.total,
            parsed=parsed,
            flags=vqs.flags,
            source_created_at=vac.source_created_at,
            category_counts_today=category_counts,
            company_counts_today=company_counts,
        )
        vac.quality_score = vqs.total
        vac.feed_score = feed.score
        vac.flags = vqs.flags
        vac.score_explanation = {
            "vqs": vqs.explanation,
            "feed": feed.explanation,
            "location": {
                "reason": location.reason,
                "work_location": location.work_location,
                "is_remote": location.is_remote,
            },
        }
        vac.scored_at = datetime.now(UTC)

        hard = {"PAYMENT_REQUIRED", "MLM_SUSPECTED", "CASINO"}
        if set(vqs.flags) & hard or vqs.total < city.min_vqs * 0.5:
            vac.moderation_status = VacancyStatus.REJECTED_AUTOMATICALLY
        else:
            vac.moderation_status = VacancyStatus.SCORED
            cat = parsed.category or "other"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            if parsed.company_name:
                key = parsed.company_name.lower().strip()
                company_counts[key] = company_counts.get(key, 0) + 1

        score = (
            await session.execute(select(VacancyScore).where(VacancyScore.vacancy_id == vac.id))
        ).scalar_one_or_none()
        if score is None:
            score = VacancyScore(vacancy_id=vac.id)
            session.add(score)
        score.salary = _component_value(vqs, "salary")
        score.workload = _component_value(vqs, "workload")
        score.flexibility = _component_value(vqs, "flexibility")
        score.company = _component_value(vqs, "company")
        score.experience_value = _component_value(vqs, "experience_value")
        score.accessibility = _component_value(vqs, "accessibility")
        score.transparency = _component_value(vqs, "transparency")
        score.vqs_total = vqs.total
        score.feed_score = feed.score
        score.components_detail = vac.score_explanation or {}
        updated += 1

    await session.flush()
    ready = await CollectionPipeline(session, settings)._rank_for_feed(city)  # noqa: SLF001
    await session.commit()
    logger.info(
        "rescore_complete",
        extra={"updated": updated, "ready": ready, "out_of_city": out_of_city},
    )
    return {"updated": updated, "ready": ready, "out_of_city": out_of_city}


async def _load_structured(session: AsyncSession, raw_item_id: Any) -> dict[str, Any] | None:
    if raw_item_id is None:
        return None
    raw = await session.get(RawItem, raw_item_id)
    if raw is None or not isinstance(raw.raw_payload, dict):
        return None
    return raw.raw_payload

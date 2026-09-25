"""Daily collection pipeline for a city."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.deduplication.service import build_fingerprint, is_near_duplicate
from app.models import (
    City,
    CollectionRun,
    CollectionRunStatus,
    Company,
    RawItem,
    RawItemStatus,
    Source,
    SourceHealthStatus,
    SourceType,
    Vacancy,
    VacancyScore,
    VacancyStatus,
)
from app.parsing.extract import parse_vacancy_text
from app.parsing.location import OUT_OF_CITY_FLAG, build_location_policy, evaluate_work_location
from app.parsing.vacancy_detect import is_vacancy_text
from app.scoring.feed_score import compute_feed_score
from app.scoring.vqs import compute_vqs
from app.sources.base import SourceAdapter
from app.sources.media import media_list_to_dicts
from app.sources.superjob import SuperJobSourceAdapter
from app.sources.trudvsem import TrudVsemSourceAdapter
from app.sources.vk import VkSourceAdapter

logger = logging.getLogger(__name__)

_STRUCTURED_SOURCES = frozenset(
    {
        SourceType.SUPERJOB,
        SourceType.TRUDVSEM,
        SourceType.HH,  # legacy rows, if any remain
    }
)


class CollectionPipeline:
    """VK + SuperJob + TrudVsem → parse → dedup → score → diversity rank."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def run_for_city(self, city_slug: str = "nizhny-novgorod") -> CollectionRun:
        city = await self._get_city(city_slug)
        run = CollectionRun(
            city_id=city.id,
            status=CollectionRunStatus.RUNNING,
            stats={},
        )
        self._session.add(run)
        await self._session.flush()

        stats: dict[str, Any] = {
            "vk_posts": 0,
            "superjob_fetched": 0,
            "trudvsem_fetched": 0,
            "vacancies_detected": 0,
            "duplicates": 0,
            "rejected": 0,
            "scored": 0,
            "ready": 0,
            "not_vacancy": 0,
            "out_of_city": 0,
            "errors": 0,
        }

        try:
            sources = await self._load_sources(city.id)
            vk_sources = [s for s in sources if s.source_type == SourceType.VK and s.enabled]
            sj_sources = [s for s in sources if s.source_type == SourceType.SUPERJOB and s.enabled]
            tv_sources = [s for s in sources if s.source_type == SourceType.TRUDVSEM and s.enabled]
            last_success_at = await self._last_successful_collection_at(city.id)

            for source in [*vk_sources, *sj_sources, *tv_sources]:
                key = {
                    SourceType.VK: "vk_posts",
                    SourceType.SUPERJOB: "superjob_fetched",
                    SourceType.TRUDVSEM: "trudvsem_fetched",
                }.get(source.source_type, "errors")
                # source_type may be plain str from DB
                st = getattr(source.source_type, "value", source.source_type)
                key = {
                    "vk": "vk_posts",
                    "superjob": "superjob_fetched",
                    "trudvsem": "trudvsem_fetched",
                }.get(str(st), key if isinstance(key, str) else "errors")
                try:
                    n = await self._collect_source(city, source, last_success_at)
                    stats[key] = int(stats.get(key) or 0) + n
                except Exception:  # noqa: BLE001
                    stats["errors"] += 1
                    source.health_status = SourceHealthStatus.ERROR
                    source.last_error = "collect_failed"
                    logger.exception(
                        "source_collect_failed",
                        extra={"source_type": st, "source_name": source.name},
                    )

            process_stats = await self._process_new_raw_items(city)
            stats.update(process_stats)

            ready = await self._rank_for_feed(city)
            stats["ready"] = ready

            run.stats = stats
            run.status = CollectionRunStatus.COMPLETED
            run.finished_at = datetime.now(UTC)
            await self._session.commit()
            return run
        except Exception as exc:  # noqa: BLE001
            run.status = CollectionRunStatus.FAILED
            run.error_message = type(exc).__name__
            run.stats = stats
            run.finished_at = datetime.now(UTC)
            await self._session.commit()
            raise

    async def _last_successful_collection_at(self, city_id: UUID) -> datetime | None:
        result = await self._session.execute(
            select(CollectionRun.finished_at)
            .where(
                CollectionRun.city_id == city_id,
                CollectionRun.status == CollectionRunStatus.COMPLETED,
                CollectionRun.finished_at.is_not(None),
            )
            .order_by(CollectionRun.finished_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_city(self, slug: str) -> City:
        result = await self._session.execute(select(City).where(City.slug == slug))
        city = result.scalar_one_or_none()
        if city is None:
            raise RuntimeError(f"city_not_found:{slug}")
        return city

    async def _load_sources(self, city_id: UUID) -> list[Source]:
        result = await self._session.execute(
            select(Source).where(Source.city_id == city_id).order_by(Source.priority, Source.name)
        )
        return list(result.scalars().all())

    async def _collect_source(
        self,
        city: City,
        source: Source,
        last_success_at: datetime | None,
    ) -> int:
        adapter = self._build_adapter(city, source, last_success_at)
        items = await adapter.fetch_new_items()
        health = await adapter.health_check()
        source.health_status = (
            SourceHealthStatus.ONLINE if health.healthy else SourceHealthStatus.ERROR
        )
        source.last_polled_at = datetime.now(UTC)
        if not health.healthy:
            source.last_error = health.detail
        else:
            source.last_error = None

        stored = 0
        newest_id = source.last_item_id
        newest_ts = source.last_timestamp
        for item in items:
            if await self._raw_exists(source.id, item.source_item_id):
                # Already imported — skip unchanged / previously seen IDs
                continue
            self._session.add(
                RawItem(
                    source_id=source.id,
                    city_id=city.id,
                    source_item_id=item.source_item_id,
                    source_url=item.source_url,
                    source_created_at=item.source_created_at,
                    first_seen_at=datetime.now(UTC),
                    raw_text=item.raw_text or "",
                    raw_payload=item.raw_payload,
                    media=media_list_to_dicts(item.media),
                    status=RawItemStatus.NEW,
                    content_hash=build_fingerprint(
                        title=None,
                        company=None,
                        salary_from=None,
                        salary_to=None,
                        contact=None,
                        text=item.raw_text or "",
                    ).content_hash,
                )
            )
            stored += 1
            if item.source_item_id.isdigit() and (
                newest_id is None
                or (newest_id.isdigit() and int(item.source_item_id) > int(newest_id))
            ) or newest_id is None or item.source_created_at is not None:
                newest_id = item.source_item_id
            if item.source_created_at and (
                newest_ts is None or item.source_created_at > newest_ts
            ):
                newest_ts = item.source_created_at

        source.last_item_id = newest_id
        source.last_timestamp = newest_ts
        await self._session.flush()
        return stored

    def _build_adapter(
        self,
        city: City,
        source: Source,
        last_success_at: datetime | None,
    ) -> SourceAdapter:
        st = getattr(source.source_type, "value", source.source_type)
        if st == SourceType.VK or st == "vk":
            return VkSourceAdapter(
                settings=self._settings,
                group_id=source.external_id,
                last_item_id=source.last_item_id,
                last_timestamp=source.last_timestamp,
            )
        if st == SourceType.SUPERJOB or st == "superjob":
            cfg = source.config if isinstance(source.config, dict) else {}
            town: str | int = cfg.get("town") or source.external_id or city.name
            return SuperJobSourceAdapter(
                settings=self._settings,
                town=town,
                last_timestamp=source.last_timestamp,
            )
        if st == SourceType.TRUDVSEM or st == "trudvsem":
            cfg = source.config if isinstance(source.config, dict) else {}
            region = (
                city.trudvsem_region_code
                or cfg.get("region_code")
                or source.external_id
            )
            if not region:
                raise RuntimeError("trudvsem_region_code_missing")
            # First poll: full regional snapshot. Later: since last successful job.
            modified_from = None if source.last_polled_at is None else last_success_at
            return TrudVsemSourceAdapter(
                settings=self._settings,
                region_code=str(region),
                modified_from=modified_from,
            )
        raise RuntimeError(f"unsupported_source_type:{source.source_type}")

    async def _raw_exists(self, source_id: UUID, source_item_id: str) -> bool:
        result = await self._session.execute(
            select(RawItem.id).where(
                RawItem.source_id == source_id,
                RawItem.source_item_id == source_item_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _process_new_raw_items(self, city: City) -> dict[str, int]:
        result = await self._session.execute(
            select(RawItem)
            .where(RawItem.city_id == city.id, RawItem.status == RawItemStatus.NEW)
            .order_by(RawItem.source_created_at.nulls_last())
        )
        raw_items = list(result.scalars().all())
        stats = {
            "vacancies_detected": 0,
            "duplicates": 0,
            "rejected": 0,
            "scored": 0,
            "not_vacancy": 0,
            "out_of_city": 0,
        }

        window_start = datetime.now(UTC) - timedelta(days=self._settings.dedup_window_days)
        recent = await self._load_recent_vacancies(city.id, window_start)
        category_counts: dict[str, int] = {}
        company_counts: dict[str, int] = {}
        location_policy = build_location_policy(
            city_name=city.name,
            region_name=city.region,
            aliases=[str(a) for a in (city.location_aliases or [])],
            allow_remote=bool(city.allow_remote),
        )
        for raw in raw_items:
            source = await self._session.get(Source, raw.source_id)
            structured_hint = False
            if source is not None:
                st = getattr(source.source_type, "value", source.source_type)
                structured_hint = st in {"superjob", "trudvsem", "hh"} or (
                    source.source_type in _STRUCTURED_SOURCES
                )
            text = raw.raw_text or ""
            if not is_vacancy_text(text, structured_hint=structured_hint):
                raw.status = RawItemStatus.SKIPPED_NOT_VACANCY
                stats["not_vacancy"] += 1
                continue

            stats["vacancies_detected"] += 1
            structured = raw.raw_payload if structured_hint else None
            structured_dict = structured if isinstance(structured, dict) else None
            parsed = parse_vacancy_text(text, structured=structured_dict)
            fp = build_fingerprint(
                title=parsed.title,
                company=parsed.company_name,
                salary_from=parsed.salary_from,
                salary_to=parsed.salary_to,
                contact=parsed.contact,
                text=text,
            )

            dup_of = self._find_duplicate(fp.fingerprint, fp.normalized_text, parsed, recent)
            company = await self._get_or_create_company(city.id, parsed.company_name)

            vacancy = Vacancy(
                city_id=city.id,
                source_id=raw.source_id,
                raw_item_id=raw.id,
                company_id=company.id if company else None,
                source_item_id=raw.source_item_id,
                source_url=raw.source_url,
                source_created_at=raw.source_created_at,
                first_seen_at=raw.first_seen_at,
                title=parsed.title,
                company_name=parsed.company_name,
                raw_text=text,
                clean_text=parsed.clean_text,
                media=list(raw.media or []),
                category=parsed.category,
                professional_role=parsed.professional_role,
                salary_from=float(parsed.salary_from) if parsed.salary_from else None,
                salary_to=float(parsed.salary_to) if parsed.salary_to else None,
                salary_currency=parsed.salary_currency,
                schedule=parsed.schedule,
                hours_per_day=parsed.hours_per_day,
                remote_type=parsed.remote_type,
                experience_required=parsed.experience_required,
                requirements=parsed.requirements,
                duties=parsed.duties,
                benefits=parsed.benefits,
                address=parsed.address,
                contact_type=parsed.contact_type,
                contact=parsed.contact,
                fingerprint=fp.fingerprint,
                collected_at=datetime.now(UTC),
                moderation_status=VacancyStatus.PARSED,
            )

            if dup_of is not None:
                vacancy.moderation_status = VacancyStatus.DUPLICATE
                vacancy.duplicate_of_id = dup_of.id
                vacancy.flags = ["DUPLICATE"]
                stats["duplicates"] += 1
                self._session.add(vacancy)
                raw.status = RawItemStatus.PROCESSED
                continue

            location = evaluate_work_location(
                text=text,
                policy=location_policy,
                address=parsed.address,
                remote_type=parsed.remote_type,
                schedule=parsed.schedule,
                structured=structured_dict,
            )
            if location.is_remote and not vacancy.remote_type:
                vacancy.remote_type = "remote"
                parsed.remote_type = "remote"
            if location.work_location and not vacancy.address:
                vacancy.address = location.work_location[:512]

            if not location.allowed:
                vacancy.moderation_status = VacancyStatus.REJECTED_AUTOMATICALLY
                vacancy.flags = [location.flag or OUT_OF_CITY_FLAG]
                vacancy.score_explanation = {
                    "location": {
                        "reason": location.reason,
                        "work_location": location.work_location,
                        "is_remote": location.is_remote,
                    }
                }
                stats["rejected"] += 1
                stats["out_of_city"] += 1
                self._session.add(vacancy)
                raw.status = RawItemStatus.PROCESSED
                recent.append(vacancy)
                continue

            vqs = compute_vqs(
                parsed,
                text,
                known_company=company is not None,
            )
            feed = compute_feed_score(
                vqs=vqs.total,
                parsed=parsed,
                flags=vqs.flags,
                source_created_at=raw.source_created_at,
                category_counts_today=category_counts,
                company_counts_today=company_counts,
            )

            vacancy.quality_score = vqs.total
            vacancy.feed_score = feed.score
            vacancy.flags = vqs.flags
            vacancy.score_explanation = {
                "vqs": vqs.explanation,
                "feed": feed.explanation,
                "location": {
                    "reason": location.reason,
                    "work_location": location.work_location,
                    "is_remote": location.is_remote,
                },
            }
            vacancy.scored_at = datetime.now(UTC)

            hard_reject_flags = {"PAYMENT_REQUIRED", "MLM_SUSPECTED", "CASINO"}
            if set(vqs.flags) & hard_reject_flags or vqs.total < city.min_vqs * 0.5:
                vacancy.moderation_status = VacancyStatus.REJECTED_AUTOMATICALLY
                stats["rejected"] += 1
            else:
                vacancy.moderation_status = VacancyStatus.SCORED
                stats["scored"] += 1
                cat = parsed.category or "other"
                category_counts[cat] = category_counts.get(cat, 0) + 1
                if parsed.company_name:
                    key = parsed.company_name.lower().strip()
                    company_counts[key] = company_counts.get(key, 0) + 1

            self._session.add(vacancy)
            await self._session.flush()
            self._session.add(
                VacancyScore(
                    vacancy_id=vacancy.id,
                    salary=_component_value(vqs, "salary"),
                    workload=_component_value(vqs, "workload"),
                    flexibility=_component_value(vqs, "flexibility"),
                    company=_component_value(vqs, "company"),
                    experience_value=_component_value(vqs, "experience_value"),
                    accessibility=_component_value(vqs, "accessibility"),
                    transparency=_component_value(vqs, "transparency"),
                    vqs_total=vqs.total,
                    feed_score=feed.score,
                    components_detail=vacancy.score_explanation or {},
                )
            )
            recent.append(vacancy)
            raw.status = RawItemStatus.PROCESSED

        await self._session.flush()
        return stats

    async def _load_recent_vacancies(self, city_id: UUID, since: datetime) -> list[Vacancy]:
        stmt: Select[tuple[Vacancy]] = select(Vacancy).where(
            Vacancy.city_id == city_id,
            Vacancy.created_at >= since,
            Vacancy.moderation_status != VacancyStatus.DUPLICATE,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    def _find_duplicate(
        self,
        fingerprint: str,
        normalized_text: str,
        parsed: Any,
        recent: list[Vacancy],
    ) -> Vacancy | None:
        for existing in recent:
            if existing.fingerprint == fingerprint:
                return existing
            if is_near_duplicate(
                parsed.title,
                parsed.company_name,
                normalized_text,
                existing.title,
                existing.company_name,
                existing.clean_text or existing.raw_text,
            ):
                return existing
        return None

    async def _get_or_create_company(self, city_id: UUID, name: str | None) -> Company | None:
        if not name:
            return None
        normalized = name.lower().strip()
        result = await self._session.execute(
            select(Company).where(
                Company.city_id == city_id,
                Company.normalized_name == normalized,
            )
        )
        company = result.scalar_one_or_none()
        if company:
            return company
        company = Company(city_id=city_id, name=name, normalized_name=normalized)
        self._session.add(company)
        await self._session.flush()
        return company

    async def _rank_for_feed(self, city: City) -> int:
        """Select top vacancies into READY_FOR_PUBLICATION ordered for VK feed."""
        # Clear previous ready ranking for this city (re-rank daily)
        result = await self._session.execute(
            select(Vacancy).where(
                Vacancy.city_id == city.id,
                Vacancy.moderation_status == VacancyStatus.READY_FOR_PUBLICATION,
            )
        )
        for old in result.scalars().all():
            old.moderation_status = VacancyStatus.SCORED
            old.ranked_position = None

        candidates = await self._session.execute(
            select(Vacancy)
            .where(
                Vacancy.city_id == city.id,
                Vacancy.moderation_status == VacancyStatus.SCORED,
                Vacancy.quality_score.is_not(None),
                Vacancy.feed_score.is_not(None),
                Vacancy.quality_score >= city.min_vqs,
                Vacancy.feed_score >= city.min_feed_score,
            )
            .order_by(Vacancy.feed_score.desc(), Vacancy.quality_score.desc())
        )
        rows = list(candidates.scalars().all())

        # Diversity-aware selection
        selected: list[Vacancy] = []
        cat_counts: dict[str, int] = {}
        company_counts: dict[str, int] = {}
        target = min(self._settings.feed_target_size, city.target_items_per_day * 2)

        for vac in rows:
            cat = vac.category or "other"
            company_key = (vac.company_name or "").lower().strip()
            if cat_counts.get(cat, 0) >= city.max_per_category_per_day:
                continue
            if company_key and company_counts.get(company_key, 0) >= city.max_per_company_per_day:
                continue
            if cat == "mass" and cat_counts.get("mass", 0) >= 2:
                continue
            selected.append(vac)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            if company_key:
                company_counts[company_key] = company_counts.get(company_key, 0) + 1
            if len(selected) >= target:
                break

        for idx, vac in enumerate(selected, start=1):
            vac.moderation_status = VacancyStatus.READY_FOR_PUBLICATION
            vac.ranked_position = idx

        await self._session.flush()
        return len(selected)


def _component_value(vqs: Any, name: str) -> float:
    for component in vqs.components:
        if component.name == name:
            return float(component.value)
    return 0.0

"""Feed and dashboard query services."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CollectionRun, Source, Vacancy, VacancyStatus
from app.schemas.feed import CollectionRunOut, DashboardStats, VacancyDetail, VacancyListItem


class FeedService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ready_feed(self, *, limit: int = 50) -> list[VacancyListItem]:
        stmt = (
            select(Vacancy, Source.source_type)
            .join(Source, Source.id == Vacancy.source_id)
            .where(Vacancy.moderation_status == VacancyStatus.READY_FOR_PUBLICATION)
            .order_by(Vacancy.ranked_position.asc().nulls_last(), Vacancy.feed_score.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        items: list[VacancyListItem] = []
        for vacancy, source_type in result.all():
            items.append(_to_list_item(vacancy, _enum_value(source_type)))
        return items

    async def vacancy_detail(self, vacancy_id: UUID) -> VacancyDetail | None:
        stmt = (
            select(Vacancy, Source.source_type)
            .join(Source, Source.id == Vacancy.source_id)
            .where(Vacancy.id == vacancy_id)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        vacancy, source_type = row
        base = _to_list_item(vacancy, _enum_value(source_type))
        return VacancyDetail(
            **base.model_dump(),
            raw_text=vacancy.raw_text,
            clean_text=vacancy.clean_text,
            requirements=vacancy.requirements,
            duties=vacancy.duties,
            benefits=vacancy.benefits,
            contact=vacancy.contact,
            score_explanation=vacancy.score_explanation,
            professional_role=vacancy.professional_role,
            remote_type=vacancy.remote_type,
            address=vacancy.address,
            district=vacancy.district,
        )

    async def dashboard(self) -> DashboardStats:
        run_result = await self._session.execute(
            select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)
        )
        last_run = run_result.scalar_one_or_none()
        run_stats = (last_run.stats if last_run else {}) or {}

        status_rows = await self._session.execute(
            select(Vacancy.moderation_status, func.count())
            .group_by(Vacancy.moderation_status)
        )
        by_status = {
            (getattr(status, "value", status)): int(count)
            for status, count in status_rows.all()
        }

        source_rows = await self._session.execute(
            select(Source.source_type, func.count())
            .join(Vacancy, Vacancy.source_id == Source.id)
            .group_by(Source.source_type)
        )
        by_source = {
            str(getattr(source_type, "value", source_type)): int(count)
            for source_type, count in source_rows.all()
        }

        avg_result = await self._session.execute(
            select(
                func.avg(Vacancy.quality_score),
                func.avg(Vacancy.feed_score),
            ).where(Vacancy.moderation_status == VacancyStatus.READY_FOR_PUBLICATION)
        )
        avg_vqs, avg_feed = avg_result.one()

        top = await self.ready_feed(limit=10)
        return DashboardStats(
            system_status="ok",
            last_collection_at=last_run.finished_at if last_run else None,
            vk_posts=by_source.get("vk", int(run_stats.get("vk_posts") or 0)),
            vacancies_detected=sum(by_status.values()),
            superjob_fetched=by_source.get("superjob", int(run_stats.get("superjob_fetched") or 0)),
            trudvsem_fetched=by_source.get(
                "trudvsem", int(run_stats.get("trudvsem_fetched") or 0)
            ),
            duplicates=by_status.get("duplicate", int(run_stats.get("duplicates") or 0)),
            rejected=by_status.get(
                "rejected_automatically", int(run_stats.get("rejected") or 0)
            ),
            ready=by_status.get(
                "ready_for_publication", int(run_stats.get("ready") or 0)
            ),
            scored=by_status.get("scored", int(run_stats.get("scored") or 0)),
            not_vacancy=int(run_stats.get("not_vacancy") or 0),
            avg_vqs=float(avg_vqs) if avg_vqs is not None else None,
            avg_feed_score=float(avg_feed) if avg_feed is not None else None,
            top_by_feed_score=top,
        )

    async def latest_run(self) -> CollectionRunOut | None:
        result = await self._session.execute(
            select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)
        )
        run = result.scalar_one_or_none()
        if run is None:
            return None
        return CollectionRunOut(
            id=run.id,
            status=run.status.value,
            started_at=run.started_at,
            finished_at=run.finished_at,
            stats=run.stats or {},
        )


def _enum_value(value: object | None) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _to_list_item(vacancy: Vacancy, source_type: str | None) -> VacancyListItem:
    media = list(vacancy.media or [])
    return VacancyListItem(
        id=vacancy.id,
        ranked_position=vacancy.ranked_position,
        title=vacancy.title,
        company_name=vacancy.company_name,
        category=vacancy.category,
        salary_from=vacancy.salary_from,
        salary_to=vacancy.salary_to,
        schedule=vacancy.schedule,
        experience_required=vacancy.experience_required,
        quality_score=vacancy.quality_score,
        feed_score=vacancy.feed_score,
        flags=list(vacancy.flags or []),
        moderation_status=vacancy.moderation_status.value
        if hasattr(vacancy.moderation_status, "value")
        else str(vacancy.moderation_status),
        source_url=vacancy.source_url,
        source_type=source_type,
        source_created_at=vacancy.source_created_at,
        media=media,
        has_media=bool(media),
    )

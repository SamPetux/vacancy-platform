"""Publication draft service — generate / regenerate / edit / approve."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.city import City
from app.models.enums import VacancyStatus
from app.models.publication_draft import PublicationDraft
from app.models.source import Source
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.engine import TemplateEngine
from app.schemas.publication import PublicationPreviewOut


class PublicationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._engine = TemplateEngine()

    async def get_or_create_preview(self, vacancy_id: UUID) -> PublicationPreviewOut | None:
        vacancy = await self._session.get(Vacancy, vacancy_id)
        if vacancy is None:
            return None
        draft_row = await self._get_draft(vacancy_id)
        if draft_row is None:
            draft_row = await self._generate(vacancy, variant=0)
        return await self._to_preview(vacancy, draft_row)

    async def regenerate(self, vacancy_id: UUID) -> PublicationPreviewOut | None:
        vacancy = await self._session.get(Vacancy, vacancy_id)
        if vacancy is None:
            return None
        existing = await self._get_draft(vacancy_id)
        next_variant = (existing.variant + 1) if existing else 0
        draft_row = await self._generate(vacancy, variant=next_variant, existing=existing)
        return await self._to_preview(vacancy, draft_row)

    async def edit(self, vacancy_id: UUID, rendered_text: str) -> PublicationPreviewOut | None:
        vacancy = await self._session.get(Vacancy, vacancy_id)
        if vacancy is None:
            return None
        draft_row = await self._get_draft(vacancy_id)
        if draft_row is None:
            draft_row = await self._generate(vacancy, variant=0)
        draft_row.rendered_text = rendered_text.strip()
        draft_row.manually_edited = True
        draft_row.status = "edited"
        await self._session.commit()
        await self._session.refresh(draft_row)
        return await self._to_preview(vacancy, draft_row)

    async def approve(self, vacancy_id: UUID) -> PublicationPreviewOut | None:
        vacancy = await self._session.get(Vacancy, vacancy_id)
        if vacancy is None:
            return None
        draft_row = await self._get_draft(vacancy_id)
        if draft_row is None:
            draft_row = await self._generate(vacancy, variant=0)
        draft_row.status = "approved"
        vacancy.moderation_status = VacancyStatus.APPROVED_FOR_PUBLICATION
        await self._session.commit()
        await self._session.refresh(draft_row)
        await self._session.refresh(vacancy)
        return await self._to_preview(vacancy, draft_row)

    async def _generate(
        self,
        vacancy: Vacancy,
        *,
        variant: int,
        existing: PublicationDraft | None = None,
    ) -> PublicationDraft:
        city = await self._session.get(City, vacancy.city_id)
        city_name = city.name if city else "Нижний Новгород"
        score = await self._session.scalar(
            select(VacancyScore).where(VacancyScore.vacancy_id == vacancy.id)
        )
        draft, text = self._engine.generate(
            vacancy,
            city_name=city_name,
            score=score,
            variant=variant,
        )
        if existing is None:
            row = PublicationDraft(
                vacancy_id=vacancy.id,
                structured=draft.model_dump_structured(),
                rendered_text=text,
                mode=draft.mode.value,
                variant=variant,
                status="draft",
                manually_edited=False,
            )
            self._session.add(row)
        else:
            row = existing
            row.structured = draft.model_dump_structured()
            row.rendered_text = text
            row.mode = draft.mode.value
            row.variant = variant
            row.status = "draft"
            row.manually_edited = False
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def _get_draft(self, vacancy_id: UUID) -> PublicationDraft | None:
        result = await self._session.execute(
            select(PublicationDraft).where(PublicationDraft.vacancy_id == vacancy_id)
        )
        return result.scalar_one_or_none()

    async def _to_preview(
        self,
        vacancy: Vacancy,
        draft: PublicationDraft,
    ) -> PublicationPreviewOut:
        source = await self._session.get(Source, vacancy.source_id)
        source_type = None
        if source is not None:
            source_type = getattr(source.source_type, "value", source.source_type)
        media = list(vacancy.media or [])
        return PublicationPreviewOut(
            vacancy_id=vacancy.id,
            source=_source_payload(vacancy, source_type),
            draft=draft.structured if isinstance(draft.structured, dict) else {},
            rendered_text=draft.rendered_text,
            mode=draft.mode,
            variant=draft.variant,
            status=draft.status,
            manually_edited=bool(draft.manually_edited),
            has_media=len(media) > 0,
        )


def _source_payload(vacancy: Vacancy, source_type: str | None) -> dict[str, Any]:
    return {
        "title": vacancy.title,
        "company_name": vacancy.company_name,
        "salary_from": vacancy.salary_from,
        "salary_to": vacancy.salary_to,
        "salary_currency": vacancy.salary_currency,
        "schedule": vacancy.schedule,
        "remote_type": vacancy.remote_type,
        "experience_required": vacancy.experience_required,
        "duties": vacancy.duties,
        "requirements": vacancy.requirements,
        "benefits": vacancy.benefits,
        "address": vacancy.address,
        "district": vacancy.district,
        "category": vacancy.category,
        "quality_score": vacancy.quality_score,
        "feed_score": vacancy.feed_score,
        "source_url": vacancy.source_url,
        "source_type": source_type,
        "raw_text": vacancy.raw_text,
        "media": list(vacancy.media or []),
    }

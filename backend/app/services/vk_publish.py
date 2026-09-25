"""Publish next ranked vacancy to the VK community wall."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.city import City
from app.models.enums import VacancyStatus
from app.models.publication_draft import PublicationDraft
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.engine import TemplateEngine
from app.publishing.vk_client import VkPublishError, VkWallPublisher, default_image_path

logger = logging.getLogger(__name__)


class VkPublishService:
    """Pick highest-ranked READY vacancy → draft → wall.post → PUBLISHED."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._engine = TemplateEngine()
        self._vk = VkWallPublisher(settings)

    async def publish_next(self, city_slug: str = "nizhny-novgorod") -> dict[str, Any]:
        if not self._settings.vk_publish_enabled:
            return {"status": "disabled", "reason": "vk_publish_enabled=false"}
        if not self._settings.vk_wall_token():
            return {"status": "error", "reason": "vk_publish_token_missing"}

        city = await self._session.scalar(select(City).where(City.slug == city_slug))
        if city is None:
            return {"status": "error", "reason": "city_not_found"}

        vacancy = await self._next_vacancy(city.id)
        if vacancy is None:
            return {"status": "empty", "reason": "no_ready_vacancies"}

        draft_row = await self._ensure_draft(vacancy, city.name)
        attachment = self._vk.resolve_default_photo_attachment(default_image_path())

        try:
            result = self._vk.post(
                draft_row.rendered_text,
                attachment=attachment,
                guid=f"vacancy-{vacancy.id}",
            )
        except VkPublishError as exc:
            logger.error(
                "vk_publish_failed",
                extra={
                    "vacancy_id": str(vacancy.id),
                    "error_code": exc.code,
                    "error": str(exc),
                },
            )
            return {
                "status": "error",
                "reason": str(exc),
                "vacancy_id": str(vacancy.id),
            }

        vacancy.moderation_status = VacancyStatus.PUBLISHED
        draft_row.status = "published"
        structured = dict(draft_row.structured or {})
        structured["vk"] = {
            "post_id": result.post_id,
            "owner_id": result.owner_id,
            "url": result.url,
            "attachment": result.attachment,
        }
        draft_row.structured = structured
        await self._session.commit()

        logger.info(
            "vk_published",
            extra={
                "vacancy_id": str(vacancy.id),
                "post_id": result.post_id,
                "url": result.url,
                "has_photo": bool(result.attachment),
            },
        )
        return {
            "status": "published",
            "vacancy_id": str(vacancy.id),
            "title": vacancy.title,
            "ranked_position": vacancy.ranked_position,
            "feed_score": vacancy.feed_score,
            "vk_url": result.url,
            "post_id": result.post_id,
            "has_photo": bool(result.attachment),
        }

    async def _next_vacancy(self, city_id: UUID) -> Vacancy | None:
        result = await self._session.execute(
            select(Vacancy)
            .where(
                Vacancy.city_id == city_id,
                Vacancy.moderation_status == VacancyStatus.READY_FOR_PUBLICATION,
            )
            .order_by(
                Vacancy.ranked_position.asc().nulls_last(),
                Vacancy.feed_score.desc().nulls_last(),
                Vacancy.quality_score.desc().nulls_last(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _ensure_draft(self, vacancy: Vacancy, city_name: str) -> PublicationDraft:
        existing_result = await self._session.execute(
            select(PublicationDraft).where(PublicationDraft.vacancy_id == vacancy.id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None and existing.rendered_text.strip():
            return existing

        score_result = await self._session.execute(
            select(VacancyScore).where(VacancyScore.vacancy_id == vacancy.id)
        )
        score = score_result.scalar_one_or_none()
        draft, text = self._engine.generate(
            vacancy,
            city_name=city_name,
            score=score,
            variant=0,
        )
        if existing is None:
            row = PublicationDraft(
                vacancy_id=vacancy.id,
                structured=draft.model_dump_structured(),
                rendered_text=text,
                mode=draft.mode.value,
                variant=0,
                status="draft",
            )
            self._session.add(row)
            await self._session.flush()
            return row

        existing.structured = draft.model_dump_structured()
        existing.rendered_text = text
        existing.mode = draft.mode.value
        await self._session.flush()
        return existing

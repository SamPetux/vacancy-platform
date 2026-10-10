"""Publish next ranked vacancy / content item to the VK community wall."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.city import City
from app.models.content_item import ContentItem
from app.models.enums import VacancyStatus
from app.models.publication_draft import PublicationDraft
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.engine import TemplateEngine
from app.publishing.vk_client import VkPublishError, VkWallPublisher, default_image_path
from app.services.content_enrichment import build_context_for_vacancy

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

        # Prefer ready ContentItem (collections) only when flag enabled
        if self._settings.content_engine_collections_enabled:
            item = await self._next_content_item(city.id)
            if item is not None and item.content_type != "VACANCY":
                return await self._publish_content_item(item, city)

        vacancy = await self._next_vacancy(city.id)
        if vacancy is None:
            return {"status": "empty", "reason": "no_ready_vacancies"}

        draft_row, content_item = await self._ensure_draft_and_item(vacancy, city)
        attachment = await self._resolve_attachment(content_item)

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

        now = datetime.now(UTC)
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
        if content_item is not None:
            content_item.status = "published"
            content_item.published_at = now
            content_item.vk_post_id = result.post_id
            content_item.vk_owner_id = result.owner_id
            content_item.vk_url = result.url
            content_item.vk_attachment = result.attachment
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
            "visual_family": (content_item.visual or {}).get("family") if content_item else None,
        }

    async def _publish_content_item(self, item: ContentItem, city: City) -> dict[str, Any]:
        text = item.rendered_text.strip()
        if not text:
            return {
                "status": "error",
                "reason": "empty_content_text",
                "content_item_id": str(item.id),
            }
        attachment = await self._resolve_attachment(item)
        try:
            result = self._vk.post(
                text,
                attachment=attachment,
                guid=f"content-{item.id}",
            )
        except VkPublishError as exc:
            item.status = "failed"
            item.error_message = str(exc)
            await self._session.commit()
            return {"status": "error", "reason": str(exc), "content_item_id": str(item.id)}

        item.status = "published"
        item.published_at = datetime.now(UTC)
        item.vk_post_id = result.post_id
        item.vk_owner_id = result.owner_id
        item.vk_url = result.url
        item.vk_attachment = result.attachment
        await self._session.commit()
        return {
            "status": "published",
            "content_item_id": str(item.id),
            "content_type": item.content_type,
            "vk_url": result.url,
            "post_id": result.post_id,
        }

    async def _resolve_attachment(self, content_item: ContentItem | None) -> str | None:
        if (
            self._settings.content_engine_visual_enabled
            and content_item is not None
            and content_item.image_path
        ):
            path = Path(content_item.image_path)
            if path.is_file():
                try:
                    return self._vk.upload_wall_photo(path)
                except VkPublishError as exc:
                    logger.warning(
                        "vk_composed_photo_upload_failed",
                        extra={"error": str(exc), "path": str(path)},
                    )
        return self._vk.resolve_default_photo_attachment(default_image_path())

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

    async def _next_content_item(self, city_id: UUID) -> ContentItem | None:
        result = await self._session.execute(
            select(ContentItem)
            .where(
                ContentItem.city_id == city_id,
                ContentItem.status == "ready",
            )
            .order_by(
                ContentItem.scheduled_at.asc().nulls_last(),
                ContentItem.ranked_position.asc().nulls_last(),
                ContentItem.created_at.asc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _ensure_draft_and_item(
        self,
        vacancy: Vacancy,
        city: City,
    ) -> tuple[PublicationDraft, ContentItem | None]:
        existing_result = await self._session.execute(
            select(PublicationDraft).where(PublicationDraft.vacancy_id == vacancy.id)
        )
        existing = existing_result.scalar_one_or_none()
        score_result = await self._session.execute(
            select(VacancyScore).where(VacancyScore.vacancy_id == vacancy.id)
        )
        score = score_result.scalar_one_or_none()

        ctx = None
        visual: dict[str, Any] = {}
        image_path: Path | None = None
        if self._settings.content_engine_visual_enabled:
            try:
                ctx, visual, image_path = await build_context_for_vacancy(
                    self._session,
                    vacancy,
                    score,
                    city_name=city.name,
                )
            except Exception as exc:  # noqa: BLE001 — fall back to default brand image
                logger.warning("visual_compose_failed", extra={"error": str(exc)})

        if existing is not None and existing.rendered_text.strip() and existing.manually_edited:
            draft_row = existing
        else:
            draft, text = self._engine.generate(
                vacancy,
                city_name=city.name,
                score=score,
                variant=0,
            )
            if ctx is not None and draft.editorial is not None:
                from app.content.markers import MARKERS, MarkerKey

                try:
                    draft.editorial.label = MARKERS[MarkerKey(ctx.creative_type)].label
                except ValueError:
                    draft.editorial.label = ctx.primary_signal.upper()
                draft.editorial.reason = ctx.editorial_reason
                draft.editorial.creative_type = ctx.creative_type
                draft.editorial.visual_family = ctx.visual_family
                draft.editorial.layout_variant = ctx.layout_variant
                draft.editorial.confidence = ctx.confidence
                draft.editorial.show_grade_publicly = False
                text = self._engine.render(draft)

            structured = draft.model_dump_structured()
            if ctx is not None:
                structured["creative_context"] = ctx.model_dump(mode="json")
                structured["visual"] = visual

            if existing is None:
                draft_row = PublicationDraft(
                    vacancy_id=vacancy.id,
                    structured=structured,
                    rendered_text=text,
                    mode=draft.mode.value,
                    variant=0,
                    status="draft",
                )
                self._session.add(draft_row)
                await self._session.flush()
            else:
                existing.structured = structured
                existing.rendered_text = text
                existing.mode = draft.mode.value
                draft_row = existing
                await self._session.flush()

        content_item = await self._upsert_vacancy_content_item(
            vacancy,
            city,
            draft_row,
            ctx_dict=ctx.model_dump(mode="json") if ctx else {},
            visual=visual,
            image_path=str(image_path) if image_path else None,
        )
        return draft_row, content_item

    async def _upsert_vacancy_content_item(
        self,
        vacancy: Vacancy,
        city: City,
        draft_row: PublicationDraft,
        *,
        ctx_dict: dict[str, Any],
        visual: dict[str, Any],
        image_path: str | None,
    ) -> ContentItem:
        existing = await self._session.scalar(
            select(ContentItem).where(
                ContentItem.vacancy_id == vacancy.id,
                ContentItem.content_type == "VACANCY",
            )
        )
        if existing is None:
            existing = ContentItem(
                city_id=city.id,
                content_type="VACANCY",
                status="ready",
                vacancy_id=vacancy.id,
            )
            self._session.add(existing)

        existing.publication_draft_id = draft_row.id
        existing.rendered_text = draft_row.rendered_text
        existing.creative_context = ctx_dict
        existing.visual = visual
        existing.image_path = image_path or visual.get("image_path")
        existing.audience_interest_score = vacancy.audience_interest_score
        existing.internal_grade = (ctx_dict or {}).get("internal_grade")
        existing.ranked_position = vacancy.ranked_position
        existing.status = "ready"
        await self._session.flush()
        return existing

"""Admin Content Engine service — planner, library, templates, analytics."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.analytics import aggregate_by_dimension, group_stats_to_dict
from app.content.markers import all_marker_options
from app.content.planner import plan_city_day
from app.content.visual.families import ACTIVE_FAMILIES, VisualFamily, default_layouts_for_family
from app.core.config import Settings, get_settings
from app.models.city import City
from app.models.content_item import ContentItem
from app.models.vacancy import Vacancy
from app.schemas.content import ContentItemOut, ContentPlanOut


class ContentAdminService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def list_items(
        self,
        *,
        city_slug: str | None = None,
        status: str | None = None,
        content_type: str | None = None,
        limit: int = 50,
    ) -> list[ContentItemOut]:
        stmt = select(ContentItem).order_by(ContentItem.created_at.desc()).limit(limit)
        if city_slug:
            city = await self._session.scalar(select(City).where(City.slug == city_slug))
            if city is None:
                return []
            stmt = stmt.where(ContentItem.city_id == city.id)
        if status:
            stmt = stmt.where(ContentItem.status == status)
        if content_type:
            stmt = stmt.where(ContentItem.content_type == content_type)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [await self._to_out(r) for r in rows]

    async def get_item(self, item_id: UUID) -> ContentItemOut | None:
        row = await self._session.get(ContentItem, item_id)
        if row is None:
            return None
        return await self._to_out(row)

    async def edit_item(self, item_id: UUID, rendered_text: str) -> ContentItemOut | None:
        row = await self._session.get(ContentItem, item_id)
        if row is None:
            return None
        row.rendered_text = rendered_text.strip()
        row.manually_edited = True
        await self._session.commit()
        await self._session.refresh(row)
        return await self._to_out(row)

    async def mark_ready(self, item_id: UUID) -> ContentItemOut | None:
        row = await self._session.get(ContentItem, item_id)
        if row is None:
            return None
        row.status = "ready"
        await self._session.commit()
        await self._session.refresh(row)
        return await self._to_out(row)

    async def plan(self, city_slug: str = "nizhny-novgorod") -> ContentPlanOut:
        city = await self._session.scalar(select(City).where(City.slug == city_slug))
        if city is None:
            return ContentPlanOut(created=[], skipped=["city_not_found"], mix_snapshot={})
        result = await plan_city_day(self._session, city, self._settings)
        await self._session.commit()
        return ContentPlanOut(
            created=result.created,
            skipped=result.skipped,
            mix_snapshot=result.mix_snapshot,
        )

    def markers(self) -> list[dict[str, str]]:
        return all_marker_options()

    def visual_families(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for fam in VisualFamily:
            out.append(
                {
                    "key": fam.value,
                    "layouts": default_layouts_for_family(fam)
                    if fam in ACTIVE_FAMILIES
                    else [],
                    "active": fam in ACTIVE_FAMILIES,
                }
            )
        return out

    async def analytics(
        self,
        *,
        city_slug: str | None = None,
        dimension: str = "visual_family",
        days: int = 30,
    ) -> list[dict[str, Any]]:
        city_id = None
        if city_slug:
            city = await self._session.scalar(select(City).where(City.slug == city_slug))
            if city is None:
                return []
            city_id = city.id
        rows = await aggregate_by_dimension(
            self._session,
            city_id=city_id,
            dimension=dimension,
            days=days,
        )
        return group_stats_to_dict(rows)

    async def image_path_for_vacancy(self, vacancy_id: UUID) -> Path | None:
        item = await self._session.scalar(
            select(ContentItem).where(
                ContentItem.vacancy_id == vacancy_id,
                ContentItem.content_type == "VACANCY",
            )
        )
        if item and item.image_path:
            path = Path(item.image_path)
            if path.is_file():
                return path
        # Fall back to structured visual on publication draft path naming
        from app.services.content_enrichment import _RENDER_DIR

        matches = list(_RENDER_DIR.glob(f"{vacancy_id}_*.png"))
        return matches[0] if matches else None

    async def _to_out(self, row: ContentItem) -> ContentItemOut:
        vqs = feed = None
        if row.vacancy_id:
            vac = await self._session.get(Vacancy, row.vacancy_id)
            if vac is not None:
                vqs = vac.quality_score
                feed = vac.feed_score
        ctx = row.creative_context or {}
        visual = row.visual or {}
        return ContentItemOut(
            id=row.id,
            city_id=row.city_id,
            content_type=row.content_type,
            status=row.status,
            vacancy_id=row.vacancy_id,
            payload=row.payload or {},
            creative_context=ctx,
            visual=visual,
            rendered_text=row.rendered_text or "",
            image_path=row.image_path,
            audience_interest_score=row.audience_interest_score,
            internal_grade=row.internal_grade,
            ranked_position=row.ranked_position,
            scheduled_at=row.scheduled_at,
            published_at=row.published_at,
            manually_edited=bool(row.manually_edited),
            vk_url=row.vk_url,
            vqs=vqs,
            feed_score=feed,
            editorial_signal=str(ctx.get("primary_signal") or ctx.get("creative_type") or ""),
            visual_template=str(visual.get("family") or ""),
        )

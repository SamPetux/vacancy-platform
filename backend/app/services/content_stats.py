"""Fetch VK post stats when the token allows; never invent values."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.content_item import ContentAnalyticsSnapshot, ContentItem
from app.publishing.vk_client import VK_API
from app.sources.http_client import redact_text

logger = logging.getLogger(__name__)


class ContentStatsService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def refresh_for_item(self, content_item_id: UUID) -> ContentAnalyticsSnapshot | None:
        item = await self._session.get(ContentItem, content_item_id)
        if item is None or item.vk_post_id is None or item.vk_owner_id is None:
            return None

        raw = self._fetch_wall_stats(owner_id=item.vk_owner_id, post_id=item.vk_post_id)
        likes = comments = reposts = views = None
        if raw:
            likes = _nested_int(raw, "likes", "count")
            comments = _nested_int(raw, "comments", "count")
            reposts = _nested_int(raw, "reposts", "count")
            views = _nested_int(raw, "views", "count")

        snap = ContentAnalyticsSnapshot(
            content_item_id=item.id,
            vk_post_id=item.vk_post_id,
            reach=None,  # require stats.getPostReach — leave null unless available
            impressions=views,
            likes=likes,
            comments=comments,
            reposts=reposts,
            hides=None,
            link_clicks=None,
            favorites=None,
            subscriber_gain=None,
            raw=raw or {"unavailable": True},
            fetched_at=datetime.now(UTC),
        )
        self._session.add(snap)
        await self._session.commit()
        await self._session.refresh(snap)
        return snap

    def _fetch_wall_stats(self, *, owner_id: int, post_id: int) -> dict[str, Any] | None:
        token = self._settings.vk_wall_token()
        if not token:
            return None
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(
                    f"{VK_API}/wall.getById",
                    params={
                        "posts": f"{owner_id}_{post_id}",
                        "access_token": token,
                        "v": self._settings.vk_api_version,
                    },
                )
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "vk_stats_fetch_failed",
                extra={"error": redact_text(str(exc))},
            )
            return None

        if data.get("error"):
            logger.info(
                "vk_stats_unavailable",
                extra={"error": data.get("error")},
            )
            return None
        response = data.get("response")
        if isinstance(response, list) and response:
            first = response[0]
            return first if isinstance(first, dict) else None
        if isinstance(response, dict):
            items = response.get("items") or []
            if items and isinstance(items[0], dict):
                return items[0]
        return None

    async def list_published_needing_stats(self, *, limit: int = 20) -> list[ContentItem]:
        result = await self._session.execute(
            select(ContentItem)
            .where(
                ContentItem.status == "published",
                ContentItem.vk_post_id.is_not(None),
            )
            .order_by(ContentItem.published_at.desc().nulls_last())
            .limit(limit)
        )
        return list(result.scalars().all())


def _nested_int(data: dict[str, Any], *keys: str) -> int | None:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    try:
        return int(cur) if cur is not None else None
    except (TypeError, ValueError):
        return None

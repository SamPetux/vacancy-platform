"""Content Analytics — aggregate effectiveness without inventing missing VK data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_item import ContentAnalyticsSnapshot, ContentItem


@dataclass(frozen=True, slots=True)
class GroupStats:
    key: str
    publications: int
    avg_reach: float | None
    avg_impressions: float | None
    reactions_per_1000: float | None
    comments_per_1000: float | None
    reposts_per_1000: float | None


def per_1000(value: int | None, base: int | None) -> float | None:
    if value is None or base is None or base <= 0:
        return None
    return round(1000.0 * value / base, 2)


async def aggregate_by_dimension(
    session: AsyncSession,
    *,
    city_id: UUID | None = None,
    dimension: str = "visual_family",
    days: int = 30,
) -> list[GroupStats]:
    """dimension: visual_family | marker | content_type | hour."""
    since = datetime.now(UTC) - timedelta(days=days)
    stmt: Select[tuple[ContentItem]] = select(ContentItem).where(
        ContentItem.status == "published",
        ContentItem.published_at.is_not(None),
        ContentItem.published_at >= since,
    )
    if city_id is not None:
        stmt = stmt.where(ContentItem.city_id == city_id)
    items = list((await session.execute(stmt)).scalars().all())
    if not items:
        return []

    ids = [i.id for i in items]
    snaps = list(
        (
            await session.execute(
                select(ContentAnalyticsSnapshot).where(
                    ContentAnalyticsSnapshot.content_item_id.in_(ids)
                )
            )
        ).scalars().all()
    )
    latest: dict[UUID, ContentAnalyticsSnapshot] = {}
    for s in snaps:
        prev = latest.get(s.content_item_id)
        if prev is None or s.fetched_at >= prev.fetched_at:
            latest[s.content_item_id] = s

    buckets: dict[str, list[tuple[ContentItem, ContentAnalyticsSnapshot | None]]] = {}
    for item in items:
        key = _dimension_key(item, dimension)
        buckets.setdefault(key, []).append((item, latest.get(item.id)))

    result: list[GroupStats] = []
    for key, rows in sorted(buckets.items(), key=lambda x: -len(x[1])):
        reaches = [s.reach for _, s in rows if s and s.reach is not None]
        imps = [s.impressions for _, s in rows if s and s.impressions is not None]
        reactions: list[tuple[int, int]] = []
        comments: list[tuple[int, int]] = []
        reposts: list[tuple[int, int]] = []
        for _, snap in rows:
            if snap is None:
                continue
            base = snap.impressions or snap.reach
            likes = snap.likes or 0
            if base and snap.likes is not None:
                reactions.append(
                    (likes + (snap.comments or 0) + (snap.reposts or 0), base)
                )
            if base and snap.comments is not None:
                comments.append((snap.comments, base))
            if base and snap.reposts is not None:
                reposts.append((snap.reposts, base))

        result.append(
            GroupStats(
                key=key,
                publications=len(rows),
                avg_reach=round(sum(reaches) / len(reaches), 1) if reaches else None,
                avg_impressions=round(sum(imps) / len(imps), 1) if imps else None,
                reactions_per_1000=_avg_per_1000(reactions),
                comments_per_1000=_avg_per_1000(comments),
                reposts_per_1000=_avg_per_1000(reposts),
            )
        )
    return result


def _avg_per_1000(pairs: list[tuple[int, int]]) -> float | None:
    if not pairs:
        return None
    rates = [1000.0 * a / b for a, b in pairs if b > 0]
    if not rates:
        return None
    return round(sum(rates) / len(rates), 2)


def _dimension_key(item: ContentItem, dimension: str) -> str:
    if dimension == "content_type":
        return item.content_type
    if dimension == "marker":
        ctx = item.creative_context or {}
        return str(ctx.get("creative_type") or (item.visual or {}).get("marker") or "unknown")
    if dimension == "hour":
        if item.published_at is None:
            return "unknown"
        return f"{item.published_at.astimezone(UTC).hour:02d}"
    # visual_family default
    visual = item.visual or {}
    return str(visual.get("family") or "unknown")


def group_stats_to_dict(rows: list[GroupStats]) -> list[dict[str, Any]]:
    return [
        {
            "key": r.key,
            "publications": r.publications,
            "avg_reach": r.avg_reach,
            "avg_impressions": r.avg_impressions,
            "reactions_per_1000": r.reactions_per_1000,
            "comments_per_1000": r.comments_per_1000,
            "reposts_per_1000": r.reposts_per_1000,
        }
        for r in rows
    ]

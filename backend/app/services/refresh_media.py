"""Refresh media assets for READY_FOR_PUBLICATION vacancies only."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import City, RawItem, Source, SourceType, Vacancy, VacancyStatus
from app.sources.http_client import SourceHttpClient
from app.sources.media import MediaAsset, extract_vk_media, media_list_to_dicts
from app.sources.superjob import SUPERJOB_API_BASE, extract_superjob_media

logger = logging.getLogger(__name__)


async def refresh_ready_media(
    session: AsyncSession,
    city_slug: str = "nizhny-novgorod",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Fetch media for current feed queue without full re-collection."""
    settings = settings or get_settings()
    city = (
        await session.execute(select(City).where(City.slug == city_slug))
    ).scalar_one_or_none()
    if city is None:
        raise RuntimeError(f"city_not_found:{city_slug}")

    result = await session.execute(
        select(Vacancy)
        .where(
            Vacancy.city_id == city.id,
            Vacancy.moderation_status == VacancyStatus.READY_FOR_PUBLICATION,
        )
        .order_by(Vacancy.ranked_position.asc().nulls_last(), Vacancy.feed_score.desc())
    )
    vacancies = list(result.scalars().all())
    source_ids = {v.source_id for v in vacancies}
    sources = {
        s.id: s
        for s in (
            await session.execute(select(Source).where(Source.id.in_(source_ids)))
        ).scalars().all()
    }

    sj_http = _superjob_client(settings)
    vk_http = SourceHttpClient(timeout=25.0, max_retries=3)

    stats: dict[str, Any] = {
        "ready": len(vacancies),
        "updated": 0,
        "no_media_found": 0,
        "errors": 0,
        "by_source": {"vk": 0, "superjob": 0, "trudvsem": 0, "other": 0},
    }

    for vacancy in vacancies:
        source = sources.get(vacancy.source_id)
        if source is None:
            stats["errors"] += 1
            continue
        try:
            media = await _fetch_media_for_vacancy(
                vacancy=vacancy,
                source=source,
                settings=settings,
                sj_http=sj_http,
                vk_http=vk_http,
            )
        except Exception:  # noqa: BLE001
            stats["errors"] += 1
            source_type = getattr(source.source_type, "value", source.source_type)
            logger.exception(
                "media_refresh_failed",
                extra={
                    "vacancy_id": str(vacancy.id),
                    "source_type": source_type,
                },
            )
            continue

        media_dicts = media_list_to_dicts(media)
        if not media_dicts:
            stats["no_media_found"] += 1
            continue

        vacancy.media = media_dicts
        if vacancy.raw_item_id:
            raw = await session.get(RawItem, vacancy.raw_item_id)
            if raw is not None:
                raw.media = media_dicts
                payload = dict(raw.raw_payload or {})
                payload["media"] = media_dicts
                raw.raw_payload = payload

        stats["updated"] += 1
        key = _source_bucket(source.source_type)
        stats["by_source"][key] = int(stats["by_source"].get(key, 0)) + 1

    await session.commit()
    return stats


def _source_bucket(source_type: SourceType | str) -> str:
    value = getattr(source_type, "value", source_type)
    if value == SourceType.VK or value == "vk":
        return "vk"
    if value == SourceType.SUPERJOB or value == "superjob":
        return "superjob"
    if value == SourceType.TRUDVSEM or value == "trudvsem":
        return "trudvsem"
    return "other"


def _superjob_client(settings: Settings) -> SourceHttpClient | None:
    secret = settings.superjob_secret_key
    if secret is None or not secret.get_secret_value().strip():
        return None
    return SourceHttpClient(
        timeout=25.0,
        max_retries=3,
        headers={
            "X-Api-App-Id": secret.get_secret_value().strip(),
            "Accept": "application/json",
        },
    )


async def _fetch_media_for_vacancy(
    *,
    vacancy: Vacancy,
    source: Source,
    settings: Settings,
    sj_http: SourceHttpClient | None,
    vk_http: SourceHttpClient,
) -> list[MediaAsset]:
    source_type = getattr(source.source_type, "value", source.source_type)

    if source_type == SourceType.SUPERJOB or source_type == "superjob":
        if sj_http is None:
            return []
        data = await sj_http.get_json(
            f"{SUPERJOB_API_BASE}/vacancies/{vacancy.source_item_id}/"
        )
        objects = data.get("objects")
        if isinstance(objects, list) and objects and isinstance(objects[0], dict):
            item: dict[str, Any] = objects[0]
        elif isinstance(data.get("vacancy"), dict):
            item = data["vacancy"]
        elif isinstance(data, dict):
            item = data
        else:
            return []
        return extract_superjob_media(item)

    if source_type == SourceType.VK or source_type == "vk":
        token = settings.vk_access_token()
        if not token:
            return []
        group_id = source.external_id.lstrip("-")
        posts = f"-{group_id}_{vacancy.source_item_id}"
        data = await vk_http.get_json(
            "https://api.vk.com/method/wall.getById",
            params={
                "posts": posts,
                "v": settings.vk_api_version,
                "access_token": token,
            },
        )
        if "error" in data:
            # Soft-fail: deleted/private posts, method restrictions, etc.
            error = data["error"] if isinstance(data["error"], dict) else {}
            logger.warning(
                "vk_media_unavailable",
                extra={
                    "error_code": error.get("error_code"),
                    "posts": posts,
                },
            )
            return []
        response = data.get("response")
        if isinstance(response, dict):
            items = response.get("items") or []
        elif isinstance(response, list):
            items = response
        else:
            items = []
        if not items or not isinstance(items[0], dict):
            return []
        return extract_vk_media(items[0].get("attachments") or [], source="vk")

    # TrudVsem / others: no reliable public images in Open Data
    return []

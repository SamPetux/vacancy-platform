"""VK wall SourceAdapter using official VK API (wall.get)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.sources.base import FetchedItem, SourceAdapter, SourceHealthResult
from app.sources.http_client import SourceHttpClient
from app.sources.media import extract_vk_media, media_list_to_dicts

logger = logging.getLogger(__name__)

VK_API_BASE = "https://api.vk.com/method"


class VkSourceAdapter(SourceAdapter):
    """Fetch new wall posts from a VK community via service/user token."""

    def __init__(
        self,
        *,
        settings: Settings,
        group_id: str,
        last_item_id: str | None = None,
        last_timestamp: datetime | None = None,
        count: int | None = None,
        http_client: SourceHttpClient | None = None,
    ) -> None:
        self._settings = settings
        self._group_id = group_id.lstrip("-")
        self._owner_id = f"-{self._group_id}"
        self._last_item_id = last_item_id
        self._last_timestamp = last_timestamp
        self._count = count or settings.vk_posts_per_source
        self._http = http_client or SourceHttpClient(timeout=25.0, max_retries=3)

    async def fetch_new_items(self) -> list[FetchedItem]:
        token = self._settings.vk_access_token()
        if not token:
            raise RuntimeError("vk_token_missing")

        data = await self._http.get_json(
            f"{VK_API_BASE}/wall.get",
            params={
                "owner_id": self._owner_id,
                "count": min(self._count, 100),
                "filter": "owner",
                "v": self._settings.vk_api_version,
                "access_token": token,
            },
        )
        if "error" in data:
            error = data["error"]
            # Never log token; only error code/message from API
            code = error.get("error_code") if isinstance(error, dict) else None
            msg = error.get("error_msg") if isinstance(error, dict) else "vk_error"
            logger.error("vk_wall_get_failed", extra={"error_code": code, "error_msg": msg})
            raise RuntimeError(f"vk_api_error:{code}")

        response = data.get("response") or {}
        items_raw = response.get("items") or []
        fetched: list[FetchedItem] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            if item.get("is_pinned"):
                # Still allow pinned if new, but typically skip re-processing via cursor
                pass
            post_id = str(item.get("id"))
            if not post_id:
                continue
            if self._is_already_seen(post_id, item.get("date")):
                continue
            text = (item.get("text") or "").strip()
            if not text and item.get("copy_history"):
                history = item["copy_history"]
                if isinstance(history, list) and history:
                    text = str(history[0].get("text") or "").strip()
            created = _unix_to_dt(item.get("date"))
            url = f"https://vk.com/wall{self._owner_id}_{post_id}"
            attachments = item.get("attachments") or []
            media = extract_vk_media(attachments, source="vk")
            # Keep lean payload: types + normalized media URLs (not full VK blobs)
            payload = {
                "id": item.get("id"),
                "owner_id": item.get("owner_id"),
                "from_id": item.get("from_id"),
                "date": item.get("date"),
                "text": item.get("text"),
                "signer_id": item.get("signer_id"),
                "marked_as_ads": item.get("marked_as_ads"),
                "attachments_types": [
                    a.get("type") for a in attachments if isinstance(a, dict)
                ],
                "media": media_list_to_dicts(media),
            }
            fetched.append(
                FetchedItem(
                    source_item_id=post_id,
                    source_url=url,
                    source_created_at=created,
                    raw_payload=payload,
                    raw_text=text or None,
                    media=media,
                )
            )
        # VK returns newest first; keep chronological for processing
        fetched.sort(key=lambda x: x.source_created_at or datetime.min.replace(tzinfo=UTC))
        logger.info(
            "vk_fetch_complete",
            extra={"group_id": self._group_id, "fetched": len(fetched)},
        )
        return fetched

    async def health_check(self) -> SourceHealthResult:
        token = self._settings.vk_access_token()
        if not token:
            return SourceHealthResult(healthy=False, detail="vk_token_missing")
        started = time.perf_counter()
        try:
            data = await self._http.get_json(
                f"{VK_API_BASE}/groups.getById",
                params={
                    "group_id": self._group_id,
                    "v": self._settings.vk_api_version,
                    "access_token": token,
                },
            )
            latency = (time.perf_counter() - started) * 1000
            if "error" in data:
                return SourceHealthResult(
                    healthy=False,
                    detail="vk_api_error",
                    latency_ms=latency,
                )
            return SourceHealthResult(healthy=True, detail="ok", latency_ms=latency)
        except Exception as exc:  # noqa: BLE001
            return SourceHealthResult(healthy=False, detail=type(exc).__name__)

    def _is_already_seen(self, post_id: str, date_unix: Any) -> bool:
        if self._last_item_id and post_id == self._last_item_id:
            return True
        if (
            self._last_item_id
            and post_id.isdigit()
            and self._last_item_id.isdigit()
            and int(post_id) <= int(self._last_item_id)
        ):
            return True
        if self._last_timestamp is not None and date_unix is not None:
            created = _unix_to_dt(date_unix)
            if created is not None and created <= self._last_timestamp:
                return True
        return False


def _unix_to_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None

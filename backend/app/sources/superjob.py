"""SuperJob official API 2.0 SourceAdapter."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings
from app.sources.base import FetchedItem, SourceAdapter, SourceHealthResult
from app.sources.http_client import SourceHttpClient
from app.sources.media import MediaAsset, media_list_to_dicts

logger = logging.getLogger(__name__)

SUPERJOB_API_BASE = "https://api.superjob.ru/2.0"

# Diversified keyword streams — not salary-sorted; scoring stays downstream.
_DEFAULT_KEYWORDS = [
    "",  # recent city stream
    "менеджер",
    "инженер",
    "разработчик",
    "аналитик",
    "маркетолог",
    "дизайнер",
    "врач",
    "учитель",
    "бухгалтер",
]


class SuperJobSourceAdapter(SourceAdapter):
    """Fetch a broad fresh SuperJob sample for a city town.

    Uses order_field=date (never payment) so high-salary mass roles do not dominate.
    Incremental mode: date_published_from from the source cursor when available.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        town: str | int,
        last_timestamp: datetime | None = None,
        per_run: int | None = None,
        keywords: list[str] | None = None,
        http_client: SourceHttpClient | None = None,
    ) -> None:
        self._settings = settings
        self._town = town
        self._last_timestamp = last_timestamp
        self._per_run = per_run or settings.superjob_vacancies_per_run
        self._keywords = keywords if keywords is not None else list(_DEFAULT_KEYWORDS)
        secret = settings.superjob_secret_key
        if secret is None or not secret.get_secret_value().strip():
            raise RuntimeError("superjob_secret_missing")
        self._http = http_client or SourceHttpClient(
            timeout=25.0,
            max_retries=3,
            headers={
                "X-Api-App-Id": secret.get_secret_value().strip(),
                "Accept": "application/json",
            },
        )

    async def fetch_new_items(self) -> list[FetchedItem]:
        per_query = max(5, self._per_run // max(1, len(self._keywords)))
        seen_ids: set[str] = set()
        fetched: list[FetchedItem] = []
        published_from = self._published_from_unix()

        for keyword in self._keywords:
            if len(fetched) >= self._per_run:
                break
            params: dict[str, Any] = {
                "town": self._town,
                "count": min(per_query, 100),
                "page": 0,
                "order_field": "date",
                "order_direction": "desc",
            }
            if published_from is not None:
                params["date_published_from"] = published_from
            else:
                params["period"] = 1  # last 24 hours on first run
            if keyword:
                params["keyword"] = keyword

            data = await self._http.get_json(f"{SUPERJOB_API_BASE}/vacancies/", params=params)
            objects = data.get("objects") or []
            for item in objects:
                if not isinstance(item, dict):
                    continue
                vacancy_id = str(item.get("id") or "")
                if not vacancy_id or vacancy_id in seen_ids:
                    continue
                seen_ids.add(vacancy_id)
                profession = str(item.get("profession") or "")
                if keyword == "" and _is_mass_role_title(profession):
                    continue
                fetched.append(self._to_fetched(item))
                if len(fetched) >= self._per_run:
                    break

        logger.info(
            "superjob_fetch_complete",
            extra={"town": str(self._town), "fetched": len(fetched)},
        )
        return fetched

    async def health_check(self) -> SourceHealthResult:
        started = time.perf_counter()
        try:
            await self._http.get_json(
                f"{SUPERJOB_API_BASE}/vacancies/",
                params={"town": self._town, "count": 1, "page": 0, "period": 1},
            )
            return SourceHealthResult(
                healthy=True,
                detail="ok",
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:  # noqa: BLE001
            return SourceHealthResult(healthy=False, detail=type(exc).__name__)

    def _published_from_unix(self) -> int | None:
        if self._last_timestamp is None:
            return None
        # Small overlap to avoid missing borderline updates
        cursor = self._last_timestamp - timedelta(minutes=30)
        return int(cursor.timestamp())

    def _to_fetched(self, item: dict[str, Any]) -> FetchedItem:
        vacancy_id = str(item["id"])
        firm_name = str(item.get("firm_name") or "")
        payment_from = item.get("payment_from") or 0
        payment_to = item.get("payment_to") or 0
        currency = str(item.get("currency") or "rub").upper()
        if currency == "RUR":
            currency = "RUB"
        experience = item.get("experience") or {}
        type_of_work = item.get("type_of_work") or {}
        place_of_work = item.get("place_of_work") or {}
        town = item.get("town") or {}
        published = item.get("date_published")
        created = _unix_to_dt(published)
        candidat = str(item.get("candidat") or "").strip()
        work = str(item.get("work") or "").strip()
        profession = str(item.get("profession") or "").strip()

        salary_payload: dict[str, Any] = {"currency": currency if currency else "RUB"}
        if payment_from:
            salary_payload["from"] = int(payment_from)
        if payment_to:
            salary_payload["to"] = int(payment_to)

        experience_name = ""
        if isinstance(experience, dict):
            experience_name = str(experience.get("title") or "")

        schedule_name = ""
        if isinstance(type_of_work, dict):
            schedule_name = str(type_of_work.get("title") or "")

        remote_hint = ""
        if isinstance(place_of_work, dict):
            remote_hint = str(place_of_work.get("title") or "")

        url = str(item.get("link") or f"https://www.superjob.ru/vakansii/{vacancy_id}.html")
        media = extract_superjob_media(item)
        parts = [
            profession,
            f"Компания: {firm_name}" if firm_name else "",
            _format_salary(salary_payload),
            f"Опыт: {experience_name}" if experience_name else "",
            f"Занятость: {schedule_name}" if schedule_name else "",
            f"Место работы: {remote_hint}" if remote_hint else "",
            candidat,
            work,
        ]
        raw_text = "\n".join(p for p in parts if p)

        # HH-compatible structured shape for shared parser (_apply_structured)
        payload = {
            "id": vacancy_id,
            "name": profession,
            "employer": {"name": firm_name or None},
            "salary": salary_payload,
            "experience": {"name": experience_name} if experience_name else None,
            "employment": {"name": schedule_name} if schedule_name else None,
            "schedule": (
                {"name": schedule_name or remote_hint}
                if (schedule_name or remote_hint)
                else None
            ),
            "published_at": created.isoformat() if created else None,
            "snippet": {
                "requirement": candidat or None,
                "responsibility": work or None,
            },
            "professional_roles": [{"name": profession}] if profession else [],
            "alternate_url": url,
            "town": town if isinstance(town, dict) else {"title": str(town) if town else None},
            "client_logo": item.get("client_logo"),
            "media": media_list_to_dicts(media),
            "source": "superjob",
        }
        return FetchedItem(
            source_item_id=vacancy_id,
            source_url=url,
            source_created_at=created,
            raw_payload=payload,
            raw_text=raw_text,
            media=media,
        )


def extract_superjob_media(item: dict[str, Any]) -> list[MediaAsset]:
    media: list[MediaAsset] = []
    logo = item.get("client_logo")
    if (
        isinstance(logo, str)
        and logo.startswith("http")
        and not logo.rstrip("/").endswith(("00000.jpg", "00000.gif", "0.jpg"))
    ):
        media.append(
            MediaAsset(
                type="logo",
                url=logo,
                source="superjob",
                external_id=str(item.get("id_client") or item.get("id") or "") or None,
            )
        )
    return media


def _format_salary(salary: dict[str, Any]) -> str:
    low = salary.get("from")
    high = salary.get("to")
    currency = salary.get("currency") or "RUB"
    if low and high:
        return f"Зарплата: {low}–{high} {currency}"
    if low:
        return f"Зарплата: от {low} {currency}"
    if high:
        return f"Зарплата: до {high} {currency}"
    return ""


def _unix_to_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


_MASS_ROLE_MARKERS = (
    "курьер",
    "грузчик",
    "дворник",
    "комплектовщик",
    "расклейщик",
    "промоутер",
    "вахта",
    "сборщик заказов",
    "упаковщик",
    "разнорабоч",
)


def _is_mass_role_title(title: str) -> bool:
    lowered = title.lower()
    return any(marker in lowered for marker in _MASS_ROLE_MARKERS)

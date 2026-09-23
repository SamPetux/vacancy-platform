"""Работа России (opendata.trudvsem.ru) SourceAdapter."""

from __future__ import annotations

import logging
import time
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.sources.base import FetchedItem, SourceAdapter, SourceHealthResult
from app.sources.http_client import SourceHttpClient

logger = logging.getLogger(__name__)

TRUDVSEM_API_BASE = "http://opendata.trudvsem.ru/api/v1"
PAGE_LIMIT = 100


class TrudVsemSourceAdapter(SourceAdapter):
    """Fetch vacancies for a configured region via official Open Data API.

    region_code is injected from City configuration — never hardcoded here.
    First run (no modified_from): full current regional snapshot with pagination.
    Later runs: only rows changed since modified_from (ISO 8601 UTC).
    """

    def __init__(
        self,
        *,
        settings: Settings,
        region_code: str,
        modified_from: datetime | None = None,
        max_pages: int | None = None,
        http_client: SourceHttpClient | None = None,
    ) -> None:
        if not region_code or not str(region_code).strip():
            raise RuntimeError("trudvsem_region_code_missing")
        self._settings = settings
        self._region_code = str(region_code).strip()
        self._modified_from = modified_from
        self._max_pages = max_pages or settings.trudvsem_max_pages
        self._http = http_client or SourceHttpClient(timeout=60.0, max_retries=3)

    async def fetch_new_items(self) -> list[FetchedItem]:
        modified_from = self._modified_from_iso()
        seen_ids: set[str] = set()
        fetched: list[FetchedItem] = []
        offset = 0

        while offset < self._max_pages:
            params: dict[str, Any] = {
                "offset": offset,
                "limit": PAGE_LIMIT,
            }
            if modified_from:
                params["modifiedFrom"] = modified_from

            url = f"{TRUDVSEM_API_BASE}/vacancies/region/{self._region_code}"
            data = await self._http.get_json(url, params=params)
            results = data.get("results") or {}
            vacancies = results.get("vacancies") or []
            if not vacancies:
                break

            for wrapper in vacancies:
                if not isinstance(wrapper, dict):
                    continue
                item = wrapper.get("vacancy") if "vacancy" in wrapper else wrapper
                if not isinstance(item, dict):
                    continue
                vacancy_id = str(item.get("id") or "")
                if not vacancy_id or vacancy_id in seen_ids:
                    continue
                seen_ids.add(vacancy_id)
                fetched.append(self._to_fetched(item))

            meta = data.get("meta") or {}
            total = int(meta.get("total") or 0)
            offset += 1
            # API offset is page index (0-based), not row offset
            if offset * PAGE_LIMIT >= total:
                break

        logger.info(
            "trudvsem_fetch_complete",
            extra={
                "region_code": self._region_code,
                "fetched": len(fetched),
                "pages": offset,
                "incremental": bool(modified_from),
            },
        )
        return fetched

    async def health_check(self) -> SourceHealthResult:
        started = time.perf_counter()
        try:
            await self._http.get_json(
                f"{TRUDVSEM_API_BASE}/vacancies/region/{self._region_code}",
                params={"offset": 0, "limit": 1},
            )
            return SourceHealthResult(
                healthy=True,
                detail="ok",
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:  # noqa: BLE001
            return SourceHealthResult(healthy=False, detail=type(exc).__name__)

    def _modified_from_iso(self) -> str | None:
        if self._modified_from is None:
            return None
        return self._modified_from.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _to_fetched(self, item: dict[str, Any]) -> FetchedItem:
        vacancy_id = str(item["id"])
        company = item.get("company") or {}
        company_name = ""
        if isinstance(company, dict):
            company_name = str(company.get("name") or "")
        job_name = str(item.get("job-name") or "")
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        requirement = item.get("requirement") or {}
        experience_years = None
        education = None
        if isinstance(requirement, dict):
            experience_years = requirement.get("experience")
            education = requirement.get("education")
        duty = str(item.get("duty") or "").strip()
        schedule = str(item.get("schedule") or "").strip()
        category = item.get("category") or {}
        specialisation = ""
        if isinstance(category, dict):
            specialisation = str(category.get("specialisation") or "")
        url = str(item.get("vac_url") or "")
        created_at = _parse_trudvsem_dt(item.get("creation-date"))
        modified_at = _parse_trudvsem_dt(item.get("date_modify"))
        # Provenance cursor prefers modification time when present
        source_created_at = modified_at or created_at
        address = _first_address(item)

        experience_name = _experience_label(experience_years)
        salary_payload: dict[str, Any] = {"currency": "RUB"}
        if salary_min is not None:
            with suppress(TypeError, ValueError):
                salary_payload["from"] = int(salary_min)
        if salary_max is not None:
            with suppress(TypeError, ValueError):
                salary_payload["to"] = int(salary_max)

        contact = _first_contact(item)
        parts = [
            job_name,
            f"Компания: {company_name}" if company_name else "",
            _format_salary(salary_payload),
            f"Опыт: {experience_name}" if experience_name else "",
            f"Образование: {education}" if education else "",
            f"График: {schedule}" if schedule else "",
            f"Адрес: {address}" if address else "",
            duty,
        ]
        raw_text = "\n".join(p for p in parts if p)

        payload = {
            "id": vacancy_id,
            "name": job_name,
            "employer": {
                "name": company_name or None,
                "inn": company.get("inn") if isinstance(company, dict) else None,
                "ogrn": company.get("ogrn") if isinstance(company, dict) else None,
                "companycode": (
                    company.get("companycode") if isinstance(company, dict) else None
                ),
            },
            "salary": salary_payload,
            "salary_raw": item.get("salary"),
            "experience": {"name": experience_name} if experience_name else None,
            "schedule": {"name": schedule} if schedule else None,
            "creation_date": created_at.isoformat() if created_at else item.get("creation-date"),
            "date_modify": modified_at.isoformat() if modified_at else item.get("date_modify"),
            "published_at": (
                created_at.isoformat() if created_at else None
            ),
            "snippet": {
                "requirement": (
                    f"опыт: {experience_name}; образование: {education}"
                    if experience_name or education
                    else None
                ),
                "responsibility": duty or None,
            },
            "professional_roles": [{"name": specialisation or job_name}],
            "alternate_url": url or None,
            "address": address,
            "contact": contact,
            "region": item.get("region"),
            "source": "trudvsem",
        }
        return FetchedItem(
            source_item_id=vacancy_id,
            source_url=url or None,
            source_created_at=source_created_at,
            raw_payload=payload,
            raw_text=raw_text,
        )


def _first_address(item: dict[str, Any]) -> str | None:
    addresses = item.get("addresses") or {}
    if not isinstance(addresses, dict):
        return None
    addr_list = addresses.get("address") or []
    if isinstance(addr_list, list) and addr_list:
        first = addr_list[0]
        if isinstance(first, dict) and first.get("location"):
            return str(first["location"])
    return None


def _first_contact(item: dict[str, Any]) -> str | None:
    contacts = item.get("contact_list") or []
    if not isinstance(contacts, list):
        return None
    for contact in contacts:
        if isinstance(contact, dict) and contact.get("contact_value"):
            return str(contact["contact_value"])
    person = item.get("contact_person")
    return str(person) if person else None


def _experience_label(years: Any) -> str:
    if years is None:
        return ""
    try:
        value = int(years)
    except (TypeError, ValueError):
        return str(years)
    if value <= 0:
        return "без опыта"
    if value == 1:
        return "от 1 года"
    if value <= 3:
        return "2–3 года"
    return f"от {value} лет"


def _format_salary(salary: dict[str, Any]) -> str:
    low = salary.get("from")
    high = salary.get("to")
    if low and high:
        return f"Зарплата: {low}–{high} RUB"
    if low:
        return f"Зарплата: от {low} RUB"
    if high:
        return f"Зарплата: до {high} RUB"
    return ""


def _parse_trudvsem_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    try:
        if len(raw) == 10 and raw[4] == "-":
            return datetime.fromisoformat(raw).replace(tzinfo=UTC)
        normalized = raw.replace("+0300", "+03:00").replace("+0400", "+04:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None

"""Backfill SuperJob work address from vacancy detail API, then rescore."""

from __future__ import annotations

import asyncio
import logging
import re

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_db, get_session_factory, init_db
from app.models import City, RawItem, Source, SourceType, Vacancy, VacancyStatus
from app.services.rescore import rescore_city
from app.sources.http_client import SourceHttpClient

logger = logging.getLogger(__name__)


async def backfill_superjob_addresses(city_slug: str = "nizhny-novgorod") -> dict[str, int]:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    secret = settings.superjob_secret_key
    if secret is None or not secret.get_secret_value().strip():
        raise RuntimeError("superjob_secret_missing")

    http = SourceHttpClient(
        timeout=25.0,
        max_retries=3,
        headers={
            "X-Api-App-Id": secret.get_secret_value().strip(),
            "Accept": "application/json",
        },
    )
    factory = get_session_factory()
    updated = 0
    checked = 0
    async with factory() as session:
        city = (
            await session.execute(select(City).where(City.slug == city_slug))
        ).scalar_one()
        rows = await session.execute(
            select(Vacancy, RawItem)
            .join(Source, Source.id == Vacancy.source_id)
            .outerjoin(RawItem, RawItem.id == Vacancy.raw_item_id)
            .where(
                Vacancy.city_id == city.id,
                Source.source_type == SourceType.SUPERJOB,
                Vacancy.moderation_status.in_(
                    [
                        VacancyStatus.SCORED,
                        VacancyStatus.READY_FOR_PUBLICATION,
                        VacancyStatus.REJECTED_AUTOMATICALLY,
                        VacancyStatus.PARSED,
                    ]
                ),
            )
        )
        for vacancy, raw in rows.all():
            checked += 1
            if not vacancy.source_item_id:
                continue
            try:
                data = await http.get_json(
                    f"https://api.superjob.ru/2.0/vacancies/{vacancy.source_item_id}/"
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "superjob_address_backfill_failed",
                    extra={"source_item_id": vacancy.source_item_id},
                )
                continue
            address = str(data.get("address") or "").strip()
            if not address:
                continue
            vacancy.address = address[:512]
            if raw is not None:
                payload = dict(raw.raw_payload or {})
                payload["address"] = address
                raw.raw_payload = payload
                if raw.raw_text and "Адрес:" not in raw.raw_text:
                    raw.raw_text = f"{raw.raw_text}\nАдрес: {address}"
                elif raw.raw_text:
                    raw.raw_text = re.sub(
                        r"(?im)^адрес\s*[:\-]\s*.+$",
                        f"Адрес: {address}",
                        raw.raw_text,
                        count=1,
                    )
            if vacancy.raw_text and "Адрес:" not in vacancy.raw_text:
                vacancy.raw_text = f"{vacancy.raw_text}\nАдрес: {address}"
            updated += 1

        await session.commit()

    result = await _rescore(city_slug)
    result = {**result, "address_checked": checked, "address_updated": updated}
    await dispose_db()
    return result


async def _rescore(city_slug: str) -> dict[str, int]:
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as session:
        return await rescore_city(session, city_slug, settings)


def main() -> None:
    out = asyncio.run(backfill_superjob_addresses())
    print(out)


if __name__ == "__main__":
    main()

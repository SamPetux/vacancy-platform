"""Seed Nizhny Novgorod city, VK groups, SuperJob and TrudVsem sources."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_db, get_session_factory, init_db
from app.models import City, ScoringConfig, Source, SourceType
from app.scoring.vqs import DEFAULT_WEIGHTS

logger = logging.getLogger(__name__)

VK_GROUPS = [
    ("109465393", "VK club109465393", "https://vk.ru/club109465393"),
    ("150929695", "VK club150929695", "https://vk.ru/club150929695"),
    ("67038698", "VK club67038698", "https://vk.ru/club67038698"),
    ("73563545", "VK club73563545", "https://vk.ru/club73563545"),
    ("39624319", "VK club39624319", "https://vk.ru/club39624319"),
    ("50477479", "VK club50477479", "https://vk.ru/club50477479"),
]

# SuperJob accepts town as name or numeric id; name is stable without a lookup call.
SUPERJOB_TOWN = "Нижний Новгород"
# OKATO/region code for Нижегородская область (TrudVsem Open Data).
TRUDVSEM_REGION = "52"


async def seed() -> None:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(select(City).where(City.slug == "nizhny-novgorod"))
        city = result.scalar_one_or_none()
        if city is None:
            city = City(
                name="Нижний Новгород",
                slug="nizhny-novgorod",
                region="Нижегородская область",
                timezone="Europe/Moscow",
                min_vqs=55,
                min_feed_score=55,
                target_items_per_day=20,
                max_per_company_per_day=2,
                max_per_category_per_day=4,
                supplement_enabled=True,
                supplement_threshold=8,
                trudvsem_region_code=TRUDVSEM_REGION,
                is_active=True,
            )
            session.add(city)
            await session.flush()
            logger.info("seeded_city", extra={"slug": city.slug})
        else:
            city.min_vqs = 50
            city.min_feed_score = 45
            city.max_per_category_per_day = 5
            city.target_items_per_day = 25
            city.supplement_enabled = True
            city.supplement_threshold = 8
            city.trudvsem_region_code = TRUDVSEM_REGION

        for external_id, name, url in VK_GROUPS:
            existing = await session.execute(
                select(Source).where(
                    Source.city_id == city.id,
                    Source.source_type == SourceType.VK,
                    Source.external_id == external_id,
                )
            )
            if existing.scalar_one_or_none() is None:
                session.add(
                    Source(
                        city_id=city.id,
                        name=name,
                        source_type=SourceType.VK,
                        external_id=external_id,
                        url=url,
                        priority=1,
                        poll_interval_minutes=1440,
                        enabled=True,
                        config={"platform": "vk"},
                    )
                )

        # Disable legacy HH sources if present
        hh_rows = await session.execute(
            select(Source).where(
                Source.city_id == city.id,
                Source.source_type == SourceType.HH,
            )
        )
        for hh_source in hh_rows.scalars().all():
            hh_source.enabled = False

        sj_existing = await session.execute(
            select(Source).where(
                Source.city_id == city.id,
                Source.source_type == SourceType.SUPERJOB,
                Source.external_id == SUPERJOB_TOWN,
            )
        )
        if sj_existing.scalar_one_or_none() is None:
            session.add(
                Source(
                    city_id=city.id,
                    name="SuperJob Нижний Новгород",
                    source_type=SourceType.SUPERJOB,
                    external_id=SUPERJOB_TOWN,
                    url="https://nn.superjob.ru/vakansii/",
                    priority=2,
                    poll_interval_minutes=1440,
                    enabled=True,
                    config={
                        "town": SUPERJOB_TOWN,
                        "role": "primary_external",
                    },
                )
            )

        tv_existing = await session.execute(
            select(Source).where(
                Source.city_id == city.id,
                Source.source_type == SourceType.TRUDVSEM,
                Source.external_id == TRUDVSEM_REGION,
            )
        )
        tv_source = tv_existing.scalar_one_or_none()
        if tv_source is None:
            session.add(
                Source(
                    city_id=city.id,
                    name="Работа России — Нижегородская область",
                    source_type=SourceType.TRUDVSEM,
                    external_id=TRUDVSEM_REGION,
                    url="https://trudvsem.ru/opendata/api",
                    priority=3,
                    poll_interval_minutes=1440,
                    enabled=True,
                    config={
                        "region_code": TRUDVSEM_REGION,
                        "role": "primary_opendata",
                    },
                )
            )
        else:
            tv_source.enabled = True
            tv_source.config = {
                "region_code": TRUDVSEM_REGION,
                "role": "primary_opendata",
            }

        scoring = await session.execute(
            select(ScoringConfig).where(
                ScoringConfig.city_id == city.id,
                ScoringConfig.is_active.is_(True),
            )
        )
        if scoring.scalar_one_or_none() is None:
            session.add(
                ScoringConfig(
                    city_id=city.id,
                    weights=DEFAULT_WEIGHTS,
                    feed_weights={
                        "vqs": 40,
                        "freshness": 15,
                        "interest": 15,
                        "career": 10,
                        "company": 5,
                        "accessibility": 5,
                    },
                    thresholds={"min_vqs": 55, "min_feed_score": 55},
                    suspicious_keywords=[
                        "пассивный доход",
                        "вложения",
                        "оплата обучения",
                    ],
                    category_coefficients={},
                    is_active=True,
                )
            )

        await session.commit()
        logger.info("seed_complete")

    await dispose_db()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

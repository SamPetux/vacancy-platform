"""CLI entrypoints."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from app.cli.seed import seed
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_db, get_session_factory, init_db
from app.services.collection import CollectionPipeline

logger = logging.getLogger(__name__)


async def collect(city_slug: str) -> None:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    factory = get_session_factory()
    async with factory() as session:
        pipeline = CollectionPipeline(session, settings)
        run = await pipeline.run_for_city(city_slug)
        print(
            json.dumps(
                {"run_id": str(run.id), "status": run.status.value, "stats": run.stats},
                ensure_ascii=False,
                indent=2,
            )
        )
    await dispose_db()


async def rescore(city_slug: str) -> None:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    factory = get_session_factory()
    async with factory() as session:
        from app.services.rescore import rescore_city

        result = await rescore_city(session, city_slug, settings)
        print(json.dumps(result, ensure_ascii=False))
    await dispose_db()


async def rerank(city_slug: str) -> None:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select

        from app.models import City

        result = await session.execute(select(City).where(City.slug == city_slug))
        city = result.scalar_one()
        city.min_vqs = 50
        city.min_feed_score = 45
        city.max_per_category_per_day = 5
        city.target_items_per_day = 25
        pipeline = CollectionPipeline(session, settings)
        ready = await pipeline._rank_for_feed(city)  # noqa: SLF001 — intentional CLI hook
        await session.commit()
        print(json.dumps({"ready": ready}, ensure_ascii=False))
    await dispose_db()


async def refresh_media(city_slug: str) -> None:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    factory = get_session_factory()
    async with factory() as session:
        from app.services.refresh_media import refresh_ready_media

        result = await refresh_ready_media(session, city_slug, settings)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    await dispose_db()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vacancy platform CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Seed Nizhny Novgorod sources")

    collect_parser = sub.add_parser("collect", help="Run daily collection pipeline")
    collect_parser.add_argument("--city", default="nizhny-novgorod")

    rerank_parser = sub.add_parser("rerank", help="Re-rank scored vacancies into feed queue")
    rerank_parser.add_argument("--city", default="nizhny-novgorod")

    rescore_parser = sub.add_parser("rescore", help="Re-parse/score vacancies and rebuild feed")
    rescore_parser.add_argument("--city", default="nizhny-novgorod")

    refresh_media_parser = sub.add_parser(
        "refresh-media",
        help="Refresh media URLs for READY_FOR_PUBLICATION vacancies only",
    )
    refresh_media_parser.add_argument("--city", default="nizhny-novgorod")

    args = parser.parse_args()
    if args.command == "seed":
        asyncio.run(seed())
    elif args.command == "collect":
        asyncio.run(collect(args.city))
    elif args.command == "rerank":
        asyncio.run(rerank(args.city))
    elif args.command == "rescore":
        asyncio.run(rescore(args.city))
    elif args.command == "refresh-media":
        asyncio.run(refresh_media(args.city))

if __name__ == "__main__":
    main()

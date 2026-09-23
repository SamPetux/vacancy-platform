"""Celery beat: daily collection."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.session import dispose_db, get_session_factory, init_db
from app.services.collection import CollectionPipeline
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.collection.collect_city")  # type: ignore[untyped-decorator]
def collect_city(city_slug: str = "nizhny-novgorod") -> dict[str, object]:
    return asyncio.run(_collect(city_slug))


async def _collect(city_slug: str) -> dict[str, object]:
    settings = get_settings()
    init_db(settings)
    factory = get_session_factory()
    try:
        async with factory() as session:
            run = await CollectionPipeline(session, settings).run_for_city(city_slug)
            return {"run_id": str(run.id), "status": run.status.value, "stats": run.stats}
    finally:
        await dispose_db()

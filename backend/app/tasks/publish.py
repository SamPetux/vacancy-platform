"""Celery: publish one vacancy to VK every N minutes."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.db.session import dispose_db, get_session_factory, init_db
from app.services.vk_publish import VkPublishService
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.publish.publish_next_vk")  # type: ignore[untyped-decorator]
def publish_next_vk(city_slug: str = "nizhny-novgorod") -> dict[str, Any]:
    return asyncio.run(_publish(city_slug))


async def _publish(city_slug: str) -> dict[str, Any]:
    settings = get_settings()
    init_db(settings)
    factory = get_session_factory()
    try:
        async with factory() as session:
            return await VkPublishService(session, settings).publish_next(city_slug)
    finally:
        await dispose_db()

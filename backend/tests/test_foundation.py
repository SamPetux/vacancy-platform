"""Configuration and SourceAdapter contract tests."""

from datetime import UTC, datetime

import pytest
from app.core.config import Settings, get_settings
from app.sources.base import FetchedItem, SourceAdapter, SourceHealthResult
from app.tasks.health import ping


def test_settings_defaults() -> None:
    get_settings.cache_clear()
    settings = Settings(
        database_url="postgresql+psycopg://u:p@localhost:5432/db",
        redis_url="redis://localhost:6379/1",
    )
    assert settings.broker_url == "redis://localhost:6379/1"
    assert settings.result_backend == "redis://localhost:6379/1"
    get_settings.cache_clear()


def test_celery_broker_override() -> None:
    settings = Settings(
        redis_url="redis://localhost:6379/0",
        celery_broker_url="redis://localhost:6379/2",
        celery_result_backend="redis://localhost:6379/3",
    )
    assert settings.broker_url == "redis://localhost:6379/2"
    assert settings.result_backend == "redis://localhost:6379/3"


def test_ping_task() -> None:
    assert ping() == {"status": "ok", "task": "ping"}


class _StubAdapter(SourceAdapter):
    async def fetch_new_items(self) -> list[FetchedItem]:
        return [
            FetchedItem(
                source_item_id="1",
                source_url="https://example.com/1",
                source_created_at=datetime.now(UTC),
                raw_text="Вакансия водителя",
            )
        ]

    async def health_check(self) -> SourceHealthResult:
        return SourceHealthResult(healthy=True, detail="ok", latency_ms=1.0)


@pytest.mark.asyncio
async def test_source_adapter_contract() -> None:
    adapter = _StubAdapter()
    items = await adapter.fetch_new_items()
    assert len(items) == 1
    assert items[0].source_item_id == "1"
    health = await adapter.health_check()
    assert health.healthy is True

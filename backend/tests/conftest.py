"""Shared pytest fixtures."""

from collections.abc import AsyncGenerator, Iterator

import pytest
from app.core.config import Settings, get_settings
from app.main import create_app
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://vacancy:vacancy@localhost:5432/vacancy",
        redis_url="redis://localhost:6379/0",
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    get_settings.cache_clear()

    def _override_settings() -> Settings:
        return settings

    application = create_app()
    application.dependency_overrides[get_settings] = _override_settings
    yield application
    application.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

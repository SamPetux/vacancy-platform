"""Health endpoint tests (no live infrastructure required for liveness/metrics)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.schemas.health import DatabaseHealthResponse, RedisHealthResponse
from app.services.health import HealthService
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"] == "vacancy-platform"
    assert "version" in payload


@pytest.mark.asyncio
async def test_metrics(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_health_db_ok(client: AsyncClient) -> None:
    mock_result = DatabaseHealthResponse(status="ok")
    with patch.object(HealthService, "check_database", new=AsyncMock(return_value=mock_result)):
        response = await client.get("/health/db")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_redis_ok(client: AsyncClient) -> None:
    mock_result = RedisHealthResponse(status="ok")
    with patch.object(HealthService, "check_redis", new=AsyncMock(return_value=mock_result)):
        response = await client.get("/health/redis")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_service_liveness(settings: object) -> None:
    from app.core.config import Settings

    assert isinstance(settings, Settings)
    engine = MagicMock()
    service = HealthService(settings=settings, engine=engine)
    result = service.liveness()
    assert result.status == "ok"
    assert result.env == "test"

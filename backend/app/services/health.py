"""Health check business logic."""

from __future__ import annotations

import time
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.core.config import Settings
from app.schemas.health import (
    DatabaseHealthResponse,
    HealthResponse,
    MetricsResponse,
    RedisHealthResponse,
)

_started_at = time.monotonic()


class HealthService:
    """Probe application and infrastructure readiness."""

    def __init__(self, settings: Settings, engine: AsyncEngine) -> None:
        self._settings = settings
        self._engine = engine

    def liveness(self) -> HealthResponse:
        """Process is up; does not check dependencies."""
        return HealthResponse(
            status="ok",
            app=self._settings.app_name,
            env=self._settings.app_env,
            version=__version__,
        )

    async def check_database(self) -> DatabaseHealthResponse:
        """Verify PostgreSQL accepts queries."""
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return DatabaseHealthResponse(status="ok")
        except Exception as exc:  # noqa: BLE001 — surface connection failures as health status
            return DatabaseHealthResponse(status="error", detail=type(exc).__name__)

    async def check_redis(self) -> RedisHealthResponse:
        """Verify Redis responds to PING."""
        client: Redis[Any] | None = None
        try:
            client = Redis.from_url(self._settings.redis_url, decode_responses=True)
            pong = await client.ping()
            if pong:
                return RedisHealthResponse(status="ok")
            return RedisHealthResponse(status="error", detail="unexpected_ping_response")
        except Exception as exc:  # noqa: BLE001
            return RedisHealthResponse(status="error", detail=type(exc).__name__)
        finally:
            if client is not None:
                await client.close()

    def metrics(self) -> MetricsResponse:
        """Return basic process metrics."""
        return MetricsResponse(uptime_seconds=time.monotonic() - _started_at)

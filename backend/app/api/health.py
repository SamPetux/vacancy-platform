"""Health and readiness HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.schemas.health import (
    DatabaseHealthResponse,
    HealthResponse,
    MetricsResponse,
    RedisHealthResponse,
)
from app.services.health import HealthService

router = APIRouter(tags=["health"])


def get_health_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthService:
    return HealthService(settings=settings, engine=get_engine())


@router.get("/health", response_model=HealthResponse)
async def health(service: Annotated[HealthService, Depends(get_health_service)]) -> HealthResponse:
    """Liveness probe — process is running."""
    return service.liveness()


@router.get("/health/db", response_model=DatabaseHealthResponse)
async def health_db(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> DatabaseHealthResponse:
    """PostgreSQL readiness probe."""
    return await service.check_database()


@router.get("/health/redis", response_model=RedisHealthResponse)
async def health_redis(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> RedisHealthResponse:
    """Redis readiness probe."""
    return await service.check_redis()


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> MetricsResponse:
    """Basic runtime metrics (expanded in later stages)."""
    return service.metrics()

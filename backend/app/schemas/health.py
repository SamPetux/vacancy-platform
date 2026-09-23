"""Health check schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """Health status of a single dependency."""

    status: Literal["ok", "error"]
    detail: str | None = None


class HealthResponse(BaseModel):
    """Aggregate application health."""

    status: Literal["ok", "degraded", "error"]
    app: str
    env: str
    version: str


class DatabaseHealthResponse(BaseModel):
    """PostgreSQL connectivity check."""

    status: Literal["ok", "error"]
    detail: str | None = None


class RedisHealthResponse(BaseModel):
    """Redis connectivity check."""

    status: Literal["ok", "error"]
    detail: str | None = None


class MetricsResponse(BaseModel):
    """Basic runtime metrics placeholder for Stage 1."""

    status: Literal["ok"] = "ok"
    uptime_seconds: float = Field(ge=0)
    note: str = "Detailed pipeline metrics arrive in later stages."

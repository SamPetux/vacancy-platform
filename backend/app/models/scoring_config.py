"""Scoring weights and thresholds — global or city-scoped."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Documented VQS component caps from docs/SCORING.md (not hard-coded in scorers).
DEFAULT_VQS_WEIGHTS: dict[str, float] = {
    "salary": 25,
    "workload": 15,
    "flexibility": 10,
    "company": 15,
    "experience_value": 15,
    "accessibility": 10,
    "transparency": 10,
}


class ScoringConfig(Base):
    """Active scoring configuration (null city_id = global default)."""

    __tablename__ = "scoring_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    city_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: dict(DEFAULT_VQS_WEIGHTS),
    )
    feed_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    thresholds: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    suspicious_keywords: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    category_coefficients: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

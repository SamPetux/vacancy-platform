"""City configuration entity — multi-city platform root."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class City(Base):
    """City with collection quotas, scoring thresholds, and supplement config."""

    __tablename__ = "cities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Europe/Moscow",
        server_default="Europe/Moscow",
    )
    # Legacy HH area id — unused in MVP (kept for historical rows).
    hh_area_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Open Data region code for Работа России (e.g. "52" for Нижегородская область).
    trudvsem_region_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Normalized name variants for work-location matching (city config, not code branches).
    location_aliases: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    # Remote roles are allowed even when work place is outside the city.
    allow_remote: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    min_vqs: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=55.0,
        server_default="55",
    )
    min_feed_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=60.0,
        server_default="60",
    )
    target_items_per_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=20,
        server_default="20",
    )
    max_per_company_per_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        server_default="2",
    )
    max_per_category_per_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )
    # When True, pull TrudVsem if primary sources leave too few scored vacancies.
    supplement_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    supplement_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=8,
        server_default="8",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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

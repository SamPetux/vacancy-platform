"""Vacancy domain entity — parsed, scored, and moderated job posting."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import VacancyStatus


class Vacancy(Base):
    """Canonical vacancy after detection, parsing, scoring, and moderation."""

    __tablename__ = "vacancies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    city_id: Mapped[UUID] = mapped_column(
        ForeignKey("cities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("raw_items.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    clean_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )

    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    professional_role: Mapped[str | None] = mapped_column(String(255), nullable=True)

    salary_from: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_to: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    salary_net_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)

    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schedule: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shifts: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hours_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    days_per_week: Mapped[float | None] = mapped_column(Float, nullable=True)

    remote_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experience_required: Mapped[str | None] = mapped_column(String(128), nullable=True)

    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    duties: Mapped[str | None] = mapped_column(Text, nullable=True)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)

    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    district: Mapped[str | None] = mapped_column(String(255), nullable=True)

    contact_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(512), nullable=True)

    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feed_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    flags: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    score_explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    moderation_status: Mapped[VacancyStatus] = mapped_column(
        String(64),
        nullable=False,
        default=VacancyStatus.NEW,
        server_default=VacancyStatus.NEW.value,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    duplicate_of_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vacancies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ranked_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

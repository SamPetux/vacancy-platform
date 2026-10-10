"""Content Engine publication unit — vacancy posts and collections."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentItem(Base):
    """Planned or published content piece for a city channel."""

    __tablename__ = "content_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    city_id: Mapped[UUID] = mapped_column(
        ForeignKey("cities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="VACANCY",
        server_default="VACANCY",
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )
    vacancy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vacancies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    publication_draft_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("publication_drafts.id", ondelete="SET NULL"),
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    creative_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    visual: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    rendered_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    vk_attachment: Mapped[str | None] = mapped_column(String(128), nullable=True)

    audience_interest_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    internal_grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ranked_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    manually_edited: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    vk_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vk_owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vk_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

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


class ContentAnalyticsSnapshot(Base):
    """VK / channel metrics snapshot — nulls when API data unavailable."""

    __tablename__ = "content_analytics_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vk_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reposts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hides: Mapped[int | None] = mapped_column(Integer, nullable=True)
    link_clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    favorites: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscriber_gain: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

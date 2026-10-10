"""Content Engine admin API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ContentItemOut(BaseModel):
    id: UUID
    city_id: UUID
    content_type: str
    status: str
    vacancy_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    creative_context: dict[str, Any] = Field(default_factory=dict)
    visual: dict[str, Any] = Field(default_factory=dict)
    rendered_text: str
    image_path: str | None = None
    audience_interest_score: float | None = None
    internal_grade: str | None = None
    ranked_position: int | None = None
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    manually_edited: bool = False
    vk_url: str | None = None
    vqs: float | None = None
    feed_score: float | None = None
    editorial_signal: str | None = None
    visual_template: str | None = None


class ContentItemEditIn(BaseModel):
    rendered_text: str = Field(min_length=20, max_length=8000)


class ContentPlanOut(BaseModel):
    created: list[UUID]
    skipped: list[str]
    mix_snapshot: dict[str, int]


class MarkerOut(BaseModel):
    key: str
    label: str
    primary_signal: str
    description: str


class VisualFamilyOut(BaseModel):
    key: str
    layouts: list[str]
    active: bool


class AnalyticsGroupOut(BaseModel):
    key: str
    publications: int
    avg_reach: float | None = None
    avg_impressions: float | None = None
    reactions_per_1000: float | None = None
    comments_per_1000: float | None = None
    reposts_per_1000: float | None = None

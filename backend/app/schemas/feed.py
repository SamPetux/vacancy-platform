"""Admin feed / analytics API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class VacancyListItem(BaseModel):
    id: UUID
    ranked_position: int | None
    title: str | None
    company_name: str | None
    category: str | None
    salary_from: float | None
    salary_to: float | None
    schedule: str | None
    experience_required: str | None
    quality_score: float | None
    feed_score: float | None
    flags: list[Any] = Field(default_factory=list)
    moderation_status: str
    source_url: str | None
    source_type: str | None = None
    source_created_at: datetime | None
    media: list[dict[str, Any]] = Field(default_factory=list)
    has_media: bool = False


class VacancyDetail(VacancyListItem):
    raw_text: str
    clean_text: str | None
    requirements: str | None
    duties: str | None
    contact: str | None
    score_explanation: dict[str, Any] | None
    professional_role: str | None
    remote_type: str | None
    address: str | None


class DashboardStats(BaseModel):
    system_status: str = "ok"
    last_collection_at: datetime | None
    vk_posts: int = 0
    vacancies_detected: int = 0
    superjob_fetched: int = 0
    trudvsem_fetched: int = 0
    duplicates: int = 0
    rejected: int = 0
    ready: int = 0
    scored: int = 0
    not_vacancy: int = 0
    avg_vqs: float | None = None
    avg_feed_score: float | None = None
    top_by_feed_score: list[VacancyListItem] = Field(default_factory=list)


class CollectionRunOut(BaseModel):
    id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    stats: dict[str, Any]

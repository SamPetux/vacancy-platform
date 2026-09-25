"""Publication preview schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PublicationPreviewOut(BaseModel):
    vacancy_id: UUID
    source: dict[str, Any]
    draft: dict[str, Any]
    rendered_text: str
    mode: str
    variant: int
    status: str
    manually_edited: bool = False
    default_image_url: str = "/brand/vacancy-default.png"
    has_media: bool = False


class PublicationEditIn(BaseModel):
    rendered_text: str = Field(min_length=20, max_length=4000)


class PublicationApproveOut(BaseModel):
    vacancy_id: UUID
    moderation_status: str
    publication_status: str

"""Intermediate publication structures (channel-agnostic)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TemplateMode(StrEnum):
    COMPACT = "compact"
    STANDARD = "standard"
    EXTENDED = "extended"


class ContentBlock(BaseModel):
    type: str
    title: str
    items: list[str] = Field(default_factory=list)
    text: str | None = None


class EditorialRating(BaseModel):
    grade: str
    label: str
    reason: str


class PostDraft(BaseModel):
    title: str
    company: str | None = None
    salary: str | None = None
    intro: str
    meta: list[str] = Field(default_factory=list)
    blocks: list[ContentBlock] = Field(default_factory=list)
    editorial: EditorialRating | None = None
    source_url: str | None = None
    mode: TemplateMode = TemplateMode.STANDARD
    variant: int = 0

    def model_dump_structured(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

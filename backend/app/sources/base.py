"""Source adapter contract.

Adapters retrieve items and preserve provenance.
They must not score, deduplicate, or parse vacancies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.sources.media import MediaAsset


@dataclass(slots=True)
class FetchedItem:
    """Normalized envelope produced by every SourceAdapter."""

    source_item_id: str
    source_url: str | None
    source_created_at: datetime | None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    raw_text: str | None = None
    media: list[MediaAsset] = field(default_factory=list)


@dataclass(slots=True)
class SourceHealthResult:
    """Adapter-level health probe result."""

    healthy: bool
    detail: str | None = None
    latency_ms: float | None = None


class SourceAdapter(ABC):
    """Common interface for all external vacancy sources."""

    @abstractmethod
    async def fetch_new_items(self) -> list[FetchedItem]:
        """Fetch only new items since the last successful cursor."""

    @abstractmethod
    async def health_check(self) -> SourceHealthResult:
        """Check whether the source is reachable and authorized."""

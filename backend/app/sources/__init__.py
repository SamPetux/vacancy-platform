"""External source adapters. Core pipeline must not depend on source-specific formats."""

from app.sources.base import FetchedItem, SourceAdapter, SourceHealthResult
from app.sources.media import MediaAsset
from app.sources.superjob import SuperJobSourceAdapter
from app.sources.trudvsem import TrudVsemSourceAdapter
from app.sources.vk import VkSourceAdapter

__all__ = [
    "FetchedItem",
    "MediaAsset",
    "SourceAdapter",
    "SourceHealthResult",
    "SuperJobSourceAdapter",
    "TrudVsemSourceAdapter",
    "VkSourceAdapter",
]

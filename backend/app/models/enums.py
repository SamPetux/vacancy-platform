"""Domain enumerations stored as plain strings in PostgreSQL."""

from enum import StrEnum


class SourceType(StrEnum):
    """Supported external source kinds."""

    VK = "vk"
    SUPERJOB = "superjob"
    TRUDVSEM = "trudvsem"
    HH = "hh"  # legacy; not used in MVP
    TELEGRAM = "telegram"
    WEBSITE = "website"
    RSS = "rss"
    CUSTOM_API = "custom_api"


class SourceHealthStatus(StrEnum):
    """Operational health of a source adapter."""

    ONLINE = "online"
    DEGRADED = "degraded"
    ERROR = "error"
    DISABLED = "disabled"
    RATE_LIMITED = "rate_limited"


class VacancyStatus(StrEnum):
    """Lifecycle / moderation status of a vacancy."""

    NEW = "new"
    NORMALIZED = "normalized"
    DUPLICATE = "duplicate"
    PARSED = "parsed"
    SCORED = "scored"
    REJECTED_AUTOMATICALLY = "rejected_automatically"
    WAITING_MODERATION = "waiting_moderation"
    READY_FOR_PUBLICATION = "ready_for_publication"
    APPROVED_FOR_PUBLICATION = "approved_for_publication"
    REJECTED_BY_MODERATOR = "rejected_by_moderator"
    ARCHIVED = "archived"
    PUBLISHED = "published"


class RawItemStatus(StrEnum):
    """Processing status of a raw collected item."""

    NEW = "new"
    PROCESSED = "processed"
    SKIPPED_NOT_VACANCY = "skipped_not_vacancy"
    ERROR = "error"


class CollectionRunStatus(StrEnum):
    """Status of a city collection run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

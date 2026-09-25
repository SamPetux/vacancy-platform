# Architecture

## Goal

Build one vacancy aggregation platform capable of serving many cities.

The application must NOT be duplicated for each city.

---

# Main pipeline

SourceAdapter
    ↓
RawItem
    ↓
Normalizer
    ↓
VacancyDetector
    ↓
DeduplicationService
    ↓
VacancyParser
    ↓
VacancyQualityScore
    ↓
FeedScore
    ↓
ModerationQueue

---

# Core entities

City

Source

RawItem

Vacancy

Company

VacancyScore

ModerationDecision

CollectionJob

SourceHealth

---

# Multi-city architecture

City is a database entity.

City configuration contains:

- name
- region
- timezone
- VQS threshold
- FeedScore threshold
- desired vacancies/day
- category quotas
- company quotas
- supplement configuration (TrudVsem when primary sources leave gaps)

Adding a city must not require application source changes.

---

# Source architecture

Every source uses SourceAdapter.

Interface concept:

class SourceAdapter:

    async def fetch_new_items(self):
        ...

    async def health_check(self):
        ...

Adapters may include:

VkSourceAdapter

SuperJobSourceAdapter

TrudVsemSourceAdapter

TelegramSourceAdapter

WebsiteSourceAdapter

RSSSourceAdapter

CustomApiSourceAdapter

FetchedItem may include `media`: a list of normalized assets
`{type, url, width?, height?, source?}` for later VK publication.

Media is stored on both RawItem and Vacancy as JSONB.

The rest of the application must not depend on source-specific formats.

MVP source tiers for a city:

1. VK communities — primary local stream
2. SuperJob API 2.0 — primary external job board (fresh broad sample, scored downstream)
3. Работа России (opendata.trudvsem.ru) — regional Open Data via `City.trudvsem_region_code`
   - first poll: full regional snapshot (`limit=100`, paginated `offset`)
   - later polls: `modifiedFrom` = last successful CollectionRun
   - no source-based scoring bias

HH.ru is out of MVP.

---

# Data processing philosophy

Cheap processing first.

Level 1:
structured fields
regex
dictionaries
rules

Level 2:
lightweight NLP

Level 3:
LLM fallback

LLM should ideally process less than 20% of vacancies.

---

# Infrastructure

API:
FastAPI

Database:
PostgreSQL

Queue:
Redis + Celery

Scheduler:
Celery Beat

Frontend:
React + TypeScript

Reverse proxy:
Caddy or nginx

Deployment:
Docker Compose initially.

---

# Current MVP

Included:

collection
normalization
deduplication
parsing
VQS
FeedScore
moderation
analytics
Telegram moderator interface
admin web dashboard
VK + SuperJob + TrudVsem (supplement)

Excluded:

HH.ru
payments
commercial placements
employer cabinet
billing
advertising

VK wall publishing is optional and gated by `VK_PUBLISH_ENABLED`.
Destination community is configured via `VK_PUBLISH_GROUP_ID` (default: Работа / Нижний).
Requires a community or user token with wall permission (`VK_PUBLISH_TOKEN`).
Default brand image is used until vacancy-native media upload is enabled.
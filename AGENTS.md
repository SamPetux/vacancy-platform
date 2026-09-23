# Project Instructions

## Project

This repository contains a scalable multi-city vacancy aggregation platform.

The first production city is Nizhny Novgorod.

The system must support adding new cities without copying or forking the application.

Main pipeline:

Source
→ RawItem
→ normalization
→ vacancy detection
→ deduplication
→ parsing
→ VQS scoring
→ FeedScore
→ moderation
→ publication queue

Automatic VK publication and paid commercial placements are NOT part of the current MVP.

---

## Core engineering principles

1. Prefer simple, maintainable solutions over clever ones.

2. Do not introduce a new dependency if the existing stack can solve the problem cleanly.

3. Do not duplicate business logic.

4. Business logic must not live inside API route handlers.

5. External data sources must be implemented through SourceAdapter.

6. City-specific logic must be configuration/data driven.

Never write:

if city == "Nizhny Novgorod":
    ...

unless there is an explicitly documented exceptional reason.

7. Scoring logic must be deterministic and explainable.

8. Never use an LLM where regex, structured fields, dictionaries or deterministic code are sufficient.

9. LLM processing is a fallback, not the default processing mechanism.

10. Do not make architectural changes without checking docs/ARCHITECTURE.md.

---

## Technology stack

Backend:
- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- Celery

Frontend:
- React
- TypeScript
- Vite
- shadcn/ui
- TanStack Query

Infrastructure:
- Docker
- Docker Compose
- Yandex Cloud

Testing:
- pytest
- pytest-asyncio
- Ruff
- mypy
- Vitest
- Playwright

---

## Database rules

All schema changes must use Alembic migrations.

Never modify the production database schema manually.

Use PostgreSQL constraints where appropriate.

Add indexes intentionally.

Avoid N+1 queries.

Use transactions for multi-step mutations.

---

## Security

Never commit secrets.

Never put credentials directly in source code.

Never print API tokens or credentials to logs.

All secrets must come from environment variables.

Validate external input.

Use least privilege.

Never expose Python stack traces through public APIs.

---

## External documentation

When working with a library or framework API that may have changed:

use Context7 before implementing.

When working with Yandex Cloud:

use the Yandex Cloud Documentation MCP.

Do not invent SDK functions or configuration parameters.

---

## Source collection

Preferred order:

1. Official API
2. RSS/feed
3. documented JSON endpoint
4. normal HTTP HTML parsing
5. browser automation only as a last resort

Do not use browser automation if a normal API exists.

Every source must implement:

- fetch_new_items
- health_check
- error handling
- retry strategy
- rate limiting

---

## Testing

A task is not complete merely because code was written.

Before declaring a task complete:

Backend changes:
- run Ruff
- run mypy
- run pytest

Frontend changes:
- run lint
- run tests
- run build

UI changes:
- verify the user flow with Playwright

Infrastructure changes:
- validate Docker Compose
- inspect service health

Fix failures before reporting completion.

---

## Definition of Done

Do not say "done" until:

1. Code is implemented.
2. Relevant tests pass.
3. Build succeeds.
4. No obvious runtime errors exist.
5. UI functionality was verified if applicable.
6. Documentation was updated if architecture changed.
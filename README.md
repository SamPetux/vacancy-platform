# Vacancy Platform

Multi-city vacancy aggregation: collect → normalize → deduplicate → score → moderate.

First production city: **Nizhny Novgorod**. Adding a city is configuration, not a new application.

> VK wall publishing is optional (`VK_PUBLISH_*`). Commercial placements are out of MVP.

## Architecture (Stage 1)

```text
SourceAdapter → RawItem → Normalizer → Detector → Dedup → Parser
    → VQS → FeedScore → ModerationQueue
```

Services (Docker Compose):

| Service     | Role                                      |
|-------------|-------------------------------------------|
| `api`       | FastAPI REST + health                     |
| `worker`    | Celery workers                            |
| `scheduler` | Celery Beat                               |
| `postgres`  | PostgreSQL 16 + `pg_trgm`                 |
| `redis`     | Broker / cache                            |
| `frontend`  | Admin SPA (scaffold)                      |
| `caddy`     | Reverse proxy (`--profile proxy`)         |

## Repository layout

```text
backend/app/   API, services, sources, scoring, tasks
frontend/      React + Vite admin UI
docker/        Caddy, Postgres init
docs/          ARCHITECTURE, SCORING, DESIGN
```

## Quick start

```bash
cp .env.example .env
# fill VK_SERVICE_TOKEN (and optional HH credentials)

# local infra (or docker compose up -d postgres redis)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.cli seed
python -m app.cli collect --city nizhny-novgorod
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend && npm install && npm run dev
```

- API: http://localhost:8000/health
- Admin feed: http://localhost:5173
- Docs: http://localhost:8000/docs

Useful CLI:

```bash
python -m app.cli rescore --city nizhny-novgorod   # rebuild scores + feed
python -m app.cli rerank --city nizhny-novgorod    # only re-rank scored rows
```

### Quality checks

```bash
make check
# or separately:
make backend-check
make frontend-check
make docker-check
```

## Health endpoints

| Path            | Purpose                |
|-----------------|------------------------|
| `GET /health`   | Liveness               |
| `GET /health/db`| PostgreSQL             |
| `GET /health/redis` | Redis              |
| `GET /metrics`  | Basic process metrics  |

## Implementation stages

1. **Foundation** (this stage) — structure, Docker, FastAPI, Redis, Celery stub
2. Domain models (City / Source / RawItem / Vacancy)
3. First SourceAdapter
4. Collection scheduler
5–9. Normalize → detect → dedup → parse → VQS → FeedScore
10. Telegram moderation bot
11. SuperJob + TrudVsem sources (HH out of MVP)
12. Admin dashboard
13. Analytics
14–15. NN MVP + second city smoke test

See `docs/ARCHITECTURE.md`, `docs/SCORING.md`, `docs/DESIGN.md`, `docs/DEPLOY.md`, and `AGENTS.md`.

## Production deploy (Yandex Cloud)

Рекомендуемый старт: **1× Compute Cloud VM** + `docker-compose.prod.yml`
(Postgres и Redis на той же машине). Подробно: [`docs/DEPLOY.md`](docs/DEPLOY.md).

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml exec api python -m app.cli seed
```

## Secrets

Never commit real tokens. Configure via `.env` (see `.env.example`):

`DATABASE_URL`, `REDIS_URL`, `TELEGRAM_BOT_TOKEN`, `VK_SERVICE_TOKEN`, `SUPERJOB_CLIENT_ID`, `SUPERJOB_SECRET_KEY`, `LLM_API_KEY`, `SENTRY_DSN`.

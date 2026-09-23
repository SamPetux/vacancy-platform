"""Lightweight Celery smoke task for foundation verification."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.health.ping")  # type: ignore[untyped-decorator]
def ping() -> dict[str, str]:
    """Return a simple payload to confirm the worker is alive."""
    return {"status": "ok", "task": "ping"}

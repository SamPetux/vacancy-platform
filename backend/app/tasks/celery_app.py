"""Celery application configuration."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "vacancy_platform",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=["app.tasks.health", "app.tasks.collection"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=60,
    task_annotations={"*": {"max_retries": 3}},
    beat_schedule={
        "daily-nn-collection": {
            "task": "app.tasks.collection.collect_city",
            "schedule": 60 * 60 * 24,
            "args": ("nizhny-novgorod",),
        },
    },
)

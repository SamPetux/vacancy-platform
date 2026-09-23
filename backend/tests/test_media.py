"""Tests for media extraction helpers and adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from app.core.config import Settings
from app.sources.media import extract_vk_media, pick_best_vk_photo_size
from app.sources.superjob import SuperJobSourceAdapter


def test_pick_best_vk_photo_size() -> None:
    best = pick_best_vk_photo_size(
        [
            {"type": "s", "url": "https://example.com/s.jpg", "width": 75, "height": 75},
            {"type": "z", "url": "https://example.com/z.jpg", "width": 1280, "height": 1024},
            {"type": "m", "url": "https://example.com/m.jpg", "width": 130, "height": 130},
        ]
    )
    assert best is not None
    assert best["url"] == "https://example.com/z.jpg"


def test_extract_vk_media_photo_and_link() -> None:
    attachments = [
        {
            "type": "photo",
            "photo": {
                "id": 11,
                "sizes": [
                    {"type": "x", "url": "https://vkcdn/photo_x.jpg", "width": 604, "height": 400},
                    {"type": "y", "url": "https://vkcdn/photo_y.jpg", "width": 807, "height": 540},
                ],
            },
        },
        {
            "type": "link",
            "link": {
                "url": "https://example.com",
                "photo": {
                    "sizes": [
                        {
                            "type": "x",
                            "url": "https://vkcdn/link.jpg",
                            "width": 500,
                            "height": 300,
                        }
                    ]
                },
            },
        },
    ]
    media = extract_vk_media(attachments)
    assert len(media) == 2
    assert media[0].type == "photo"
    assert media[0].url == "https://vkcdn/photo_y.jpg"
    assert media[1].type == "link_preview"


class _FakeHttp:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self.payload


@pytest.mark.asyncio
async def test_superjob_stores_client_logo_media() -> None:
    settings = Settings(superjob_secret_key="test-secret", superjob_vacancies_per_run=5)
    http = _FakeHttp(
        {
            "objects": [
                {
                    "id": 201,
                    "profession": "Маркетолог",
                    "firm_name": "КуулКлевер",
                    "client_logo": "https://public.superjob.ru/images/clients_logos.ru/123.jpg",
                    "payment_from": 100000,
                    "payment_to": 0,
                    "currency": "rub",
                    "date_published": int(datetime(2026, 9, 22, tzinfo=UTC).timestamp()),
                    "candidat": "",
                    "work": "",
                    "experience": {"title": "От 1 года"},
                    "type_of_work": {"title": "Полная занятость"},
                    "place_of_work": {"title": "На месте работодателя"},
                    "link": "https://www.superjob.ru/vakansii/201.html",
                    "town": {"id": 1, "title": "Нижний Новгород"},
                }
            ]
        }
    )
    adapter = SuperJobSourceAdapter(
        settings=settings,
        town="Нижний Новгород",
        keywords=[""],
        http_client=http,  # type: ignore[arg-type]
    )
    items = await adapter.fetch_new_items()
    assert len(items) == 1
    assert len(items[0].media) == 1
    assert items[0].media[0].type == "logo"
    assert "123.jpg" in items[0].media[0].url

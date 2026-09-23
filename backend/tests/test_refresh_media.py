"""Tests for READY feed media refresh."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.models import SourceType
from app.services.refresh_media import _fetch_media_for_vacancy


@pytest.mark.asyncio
async def test_fetch_superjob_media_for_vacancy() -> None:
    settings = Settings(superjob_secret_key="secret")
    vacancy = MagicMock()
    vacancy.source_item_id = "52216846"
    source = MagicMock()
    source.source_type = SourceType.SUPERJOB
    source.external_id = "Нижний Новгород"

    http = AsyncMock()
    http.get_json = AsyncMock(
        return_value={
            "id": 52216846,
            "client_logo": "https://public.superjob.ru/images/clients_logos.ru/abc.jpg",
            "profession": "Инженер",
        }
    )

    media = await _fetch_media_for_vacancy(
        vacancy=vacancy,
        source=source,
        settings=settings,
        sj_http=http,
        vk_http=AsyncMock(),
    )
    assert len(media) == 1
    assert media[0].type == "logo"
    http.get_json.assert_awaited()


@pytest.mark.asyncio
async def test_fetch_vk_media_for_vacancy() -> None:
    settings = Settings(vk_service_token="vk-token")
    vacancy = MagicMock()
    vacancy.source_item_id = "123"
    vacancy.id = uuid4()
    source = MagicMock()
    source.source_type = SourceType.VK
    source.external_id = "109465393"

    http = AsyncMock()
    http.get_json = AsyncMock(
        return_value={
            "response": [
                {
                    "id": 123,
                    "attachments": [
                        {
                            "type": "photo",
                            "photo": {
                                "id": 1,
                                "sizes": [
                                    {
                                        "type": "z",
                                        "url": "https://vkcdn/big.jpg",
                                        "width": 1000,
                                        "height": 800,
                                    }
                                ],
                            },
                        }
                    ],
                }
            ]
        }
    )

    media = await _fetch_media_for_vacancy(
        vacancy=vacancy,
        source=source,
        settings=settings,
        sj_http=None,
        vk_http=http,
    )
    assert len(media) == 1
    assert media[0].url == "https://vkcdn/big.jpg"
    params: dict[str, Any] = http.get_json.await_args.kwargs["params"]
    assert params["posts"] == "-109465393_123"

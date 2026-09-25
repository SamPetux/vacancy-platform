"""Tests for VK wall publisher (mocked HTTP)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.core.config import Settings
from app.publishing.vk_client import VkPublishError, VkWallPublisher, default_image_path
from pydantic import SecretStr


def test_default_image_exists() -> None:
    path = default_image_path()
    assert path.is_file()
    assert path.suffix == ".png"


def test_wall_post_builds_attachment() -> None:
    settings = Settings(
        vk_publish_group_id="241679288",
        vk_publish_token=SecretStr("test-token"),
        vk_api_version="5.199",
    )
    publisher = VkWallPublisher(settings)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": {"post_id": 42}}

    with patch("app.publishing.vk_client.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.post.return_value = mock_response
        client_cls.return_value = client

        result = publisher.post("Тест пост", attachment="photo-241679288_1", guid="g1")

    assert result.post_id == 42
    assert result.url == "https://vk.com/wall-241679288_42"
    assert result.attachment == "photo-241679288_1"
    sent = client.post.call_args
    assert sent.args[0].endswith("/wall.post")
    data = sent.kwargs["data"]
    assert data["owner_id"] == -241679288
    assert data["from_group"] == 1
    assert data["attachments"] == "photo-241679288_1"
    assert "access_token" in data


def test_wall_post_raises_on_api_error() -> None:
    settings = Settings(
        vk_publish_group_id="241679288",
        vk_publish_token=SecretStr("test-token"),
    )
    publisher = VkWallPublisher(settings)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "error": {"error_code": 28, "error_msg": "service token"},
    }
    with patch("app.publishing.vk_client.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.post.return_value = mock_response
        client_cls.return_value = client
        with pytest.raises(VkPublishError) as exc:
            publisher.post("x")
    assert exc.value.code == 28


def test_resolve_photo_uses_cached_attachment(tmp_path: Path) -> None:
    settings = Settings(
        vk_publish_group_id="241679288",
        vk_publish_token=SecretStr("test-token"),
        vk_publish_photo_attachment="photo-1_2",
    )
    publisher = VkWallPublisher(settings)
    assert publisher.resolve_default_photo_attachment(tmp_path / "missing.png") == "photo-1_2"

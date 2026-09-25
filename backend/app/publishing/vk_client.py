"""VK wall publisher — wall.post + optional wall photo upload."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from app.sources.http_client import redact_text

logger = logging.getLogger(__name__)

VK_API = "https://api.vk.com/method"


class VkPublishError(RuntimeError):
    """Raised when VK publish API returns an error."""

    def __init__(self, code: int | None, message: str) -> None:
        self.code = code
        super().__init__(f"vk_error:{code}:{message}")


@dataclass(frozen=True)
class VkPostResult:
    post_id: int
    owner_id: int
    attachment: str | None
    url: str


class VkWallPublisher:
    """Post editorial text (+ optional photo) to a community wall."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._group_id = int(str(settings.vk_publish_group_id).lstrip("-"))
        self._owner_id = -self._group_id
        self._api_version = settings.vk_api_version

    @property
    def group_id(self) -> int:
        return self._group_id

    def post(
        self,
        message: str,
        *,
        attachment: str | None = None,
        guid: str | None = None,
    ) -> VkPostResult:
        token = self._settings.vk_wall_token()
        if not token:
            raise VkPublishError(None, "vk_publish_token_missing")

        params: dict[str, Any] = {
            "owner_id": self._owner_id,
            "from_group": 1,
            "message": message.strip(),
            "access_token": token,
            "v": self._api_version,
        }
        if attachment:
            params["attachments"] = attachment
        if guid:
            params["guid"] = guid

        data = self._api("wall.post", params)
        response = data.get("response") or {}
        post_id = int(response["post_id"])
        return VkPostResult(
            post_id=post_id,
            owner_id=self._owner_id,
            attachment=attachment,
            url=f"https://vk.com/wall{self._owner_id}_{post_id}",
        )

    def resolve_default_photo_attachment(self, image_path: Path) -> str | None:
        """Return photo attachment id: env cache → upload → None on failure."""
        cached = (self._settings.vk_publish_photo_attachment or "").strip()
        if cached:
            return cached
        try:
            return self.upload_wall_photo(image_path)
        except VkPublishError as exc:
            logger.warning(
                "vk_photo_upload_failed",
                extra={"error_code": exc.code, "error": str(exc)},
            )
            return None

    def upload_wall_photo(self, image_path: Path) -> str:
        """Upload local image via photos.getWallUploadServer → saveWallPhoto.

        Requires a *user* token with photos permission for the group.
        Community tokens typically return error 27 for this method.
        """
        token = self._settings.vk_photo_upload_token()
        if not token:
            raise VkPublishError(None, "vk_photo_upload_token_missing")
        if not image_path.is_file():
            raise VkPublishError(None, f"image_missing:{image_path}")

        server = self._api(
            "photos.getWallUploadServer",
            {
                "group_id": self._group_id,
                "access_token": token,
                "v": self._api_version,
            },
        )
        upload_url = (server.get("response") or {}).get("upload_url")
        if not upload_url:
            raise VkPublishError(None, "upload_url_missing")

        with image_path.open("rb") as fh, httpx.Client(timeout=60.0, trust_env=False) as client:
            uploaded = client.post(upload_url, files={"photo": fh})
            uploaded.raise_for_status()
            payload = uploaded.json()

        if not isinstance(payload, dict) or "photo" not in payload:
            raise VkPublishError(None, "upload_payload_invalid")

        saved = self._api(
            "photos.saveWallPhoto",
            {
                "group_id": self._group_id,
                "server": payload.get("server"),
                "photo": payload.get("photo"),
                "hash": payload.get("hash"),
                "access_token": token,
                "v": self._api_version,
            },
        )
        photos = saved.get("response") or []
        if not photos or not isinstance(photos[0], dict):
            raise VkPublishError(None, "save_wall_photo_empty")
        photo = photos[0]
        owner_id = int(photo["owner_id"])
        photo_id = int(photo["id"])
        attachment = f"photo{owner_id}_{photo_id}"
        logger.info("vk_photo_uploaded", extra={"attachment": attachment})
        return attachment

    def _api(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=30.0, trust_env=False) as client:
            response = client.post(f"{VK_API}/{method}", data=params)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise VkPublishError(None, "invalid_json")
        if "error" in data:
            err = data["error"] if isinstance(data["error"], dict) else {}
            code = err.get("error_code")
            msg = redact_text(str(err.get("error_msg") or "unknown"))
            # Never log access_token
            logger.error(
                "vk_api_error",
                extra={"method": method, "error_code": code, "error_msg": msg},
            )
            raise VkPublishError(int(code) if code is not None else None, msg)
        return data


def default_image_path() -> Path:
    """Repo brand fallback image for posts without vacancy media."""
    root = Path(__file__).resolve().parents[3]
    candidates = [
        root / "assets" / "brand" / "vacancy-default.png",
        root / "frontend" / "public" / "brand" / "vacancy-default.png",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]

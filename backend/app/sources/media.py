"""Normalized media assets for later VK publication."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

MediaKind = Literal["photo", "logo", "link_preview", "doc", "video_cover"]


@dataclass(slots=True)
class MediaAsset:
    """Source-agnostic media reference stored on RawItem / Vacancy."""

    type: MediaKind
    url: str
    width: int | None = None
    height: int | None = None
    source: str | None = None
    external_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


def media_list_to_dicts(items: list[MediaAsset]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in items]


def dedupe_media(items: list[MediaAsset]) -> list[MediaAsset]:
    seen: set[str] = set()
    result: list[MediaAsset] = []
    for item in items:
        url = item.url.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(item)
    return result


def pick_best_vk_photo_size(sizes: list[Any]) -> dict[str, Any] | None:
    """Pick the largest VK photo size object from wall.get attachments."""
    best: dict[str, Any] | None = None
    best_area = -1
    for size in sizes:
        if not isinstance(size, dict):
            continue
        url = size.get("url")
        if not url:
            continue
        width = int(size.get("width") or 0)
        height = int(size.get("height") or 0)
        area = width * height
        # Prefer typed largest when area missing
        type_rank = {"w": 6, "z": 5, "y": 4, "x": 3, "m": 2, "s": 1}.get(
            str(size.get("type") or ""), 0
        )
        score = area if area > 0 else type_rank
        if score > best_area:
            best_area = score
            best = size
    return best


def extract_vk_media(attachments: Any, *, source: str = "vk") -> list[MediaAsset]:
    """Extract publishable media URLs from VK wall attachments."""
    if not isinstance(attachments, list):
        return []
    media: list[MediaAsset] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        kind = attachment.get("type")
        if kind == "photo":
            photo = attachment.get("photo") or {}
            if not isinstance(photo, dict):
                continue
            best = pick_best_vk_photo_size(photo.get("sizes") or [])
            if best and best.get("url"):
                media.append(
                    MediaAsset(
                        type="photo",
                        url=str(best["url"]),
                        width=int(best["width"]) if best.get("width") else None,
                        height=int(best["height"]) if best.get("height") else None,
                        source=source,
                        external_id=(
                            str(photo.get("id")) if photo.get("id") is not None else None
                        ),
                    )
                )
        elif kind == "link":
            link = attachment.get("link") or {}
            if not isinstance(link, dict):
                continue
            photo = link.get("photo") or {}
            if isinstance(photo, dict):
                best = pick_best_vk_photo_size(photo.get("sizes") or [])
                if best and best.get("url"):
                    media.append(
                        MediaAsset(
                            type="link_preview",
                            url=str(best["url"]),
                            width=int(best["width"]) if best.get("width") else None,
                            height=int(best["height"]) if best.get("height") else None,
                            source=source,
                        )
                    )
        elif kind == "doc":
            doc = attachment.get("doc") or {}
            if not isinstance(doc, dict):
                continue
            # VK image documents often expose preview or url
            url = doc.get("url")
            preview = doc.get("preview") or {}
            if isinstance(preview, dict):
                photo = preview.get("photo") or {}
                if isinstance(photo, dict):
                    best = pick_best_vk_photo_size(photo.get("sizes") or [])
                    if best and best.get("url"):
                        media.append(
                            MediaAsset(
                                type="doc",
                                url=str(best["url"]),
                                width=int(best["width"]) if best.get("width") else None,
                                height=int(best["height"]) if best.get("height") else None,
                                source=source,
                                external_id=(
                                    str(doc.get("id")) if doc.get("id") is not None else None
                                ),
                            )
                        )
                        continue
            if url and str(doc.get("ext") or "").lower() in {"jpg", "jpeg", "png", "gif", "webp"}:
                media.append(
                    MediaAsset(
                        type="doc",
                        url=str(url),
                        source=source,
                        external_id=str(doc.get("id")) if doc.get("id") is not None else None,
                    )
                )
        elif kind == "video":
            video = attachment.get("video") or {}
            if not isinstance(video, dict):
                continue
            # Prefer highest image from video.image list
            images = video.get("image") or video.get("first_frame") or []
            if isinstance(images, list) and images:
                best = max(
                    (img for img in images if isinstance(img, dict) and img.get("url")),
                    key=lambda img: int(img.get("width") or 0) * int(img.get("height") or 0),
                    default=None,
                )
                if best and best.get("url"):
                    media.append(
                        MediaAsset(
                            type="video_cover",
                            url=str(best["url"]),
                            width=int(best["width"]) if best.get("width") else None,
                            height=int(best["height"]) if best.get("height") else None,
                            source=source,
                            external_id=(
                                str(video.get("id")) if video.get("id") is not None else None
                            ),
                        )
                    )
    return dedupe_media(media)

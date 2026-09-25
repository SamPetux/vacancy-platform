"""Bullet extraction and light compression for content blocks."""

from __future__ import annotations

import re

_BULLET_RE = re.compile(
    r"(?m)^\s*(?:[•●▪\*]|[-–—]|\d+[.)])\s+(.+?)(?:\s*$)"
)
_SPLIT_RE = re.compile(r"(?<=[.;])\s+|\n+")


def extract_bullets(text: str | None, *, limit: int = 4, max_len: int = 110) -> list[str]:
    if not text:
        return []
    cleaned = text.strip()
    bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(cleaned)]
    if len(bullets) < 2:
        # Sentence / clause split as fallback
        parts = [p.strip(" ;.-") for p in _SPLIT_RE.split(cleaned) if p.strip()]
        bullets = [p for p in parts if 12 <= len(p) <= 220]
    result: list[str] = []
    seen: set[str] = set()
    for item in bullets:
        compact = _compress(item, max_len=max_len)
        key = compact.lower()
        if key in seen or len(compact) < 8:
            continue
        if _is_hr_noise(compact):
            continue
        seen.add(key)
        result.append(compact)
        if len(result) >= limit:
            break
    return result


def prose_summary(text: str | None, *, max_len: int = 220) -> str | None:
    bullets = extract_bullets(text, limit=3, max_len=90)
    if bullets:
        joined = "; ".join(bullets)
        return _compress(joined, max_len=max_len)
    if not text:
        return None
    one_line = re.sub(r"\s+", " ", text).strip()
    return _compress(one_line, max_len=max_len) or None


def _compress(text: str, *, max_len: int) -> str:
    text = re.sub(r"\s+", " ", text).strip(" ;,.")
    text = re.sub(r"(?i)^(обязанности|требования|условия)\s*[:\-–—]\s*", "", text)
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;.") + "…"


def _is_hr_noise(text: str) -> bool:
    lowered = text.lower()
    noise = (
        "рассмотрим резюме",
        "ждём именно тебя",
        "работа мечты",
        "уникальная возможность",
        "успей откликнуться",
        "команда мечты",
    )
    return any(n in lowered for n in noise)

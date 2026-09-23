"""Deduplication helpers — exact + near-duplicate within a time window."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from rapidfuzz import fuzz


@dataclass
class FingerprintParts:
    fingerprint: str
    content_hash: str
    normalized_text: str


def normalize_text(text: str) -> str:
    lowered = text.lower().replace("ё", "е")
    lowered = re.sub(r"https?://\S+", " ", lowered)
    lowered = re.sub(r"[^\w\s+]", " ", lowered, flags=re.UNICODE)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def build_fingerprint(
    *,
    title: str | None,
    company: str | None,
    salary_from: int | None,
    salary_to: int | None,
    contact: str | None,
    text: str,
) -> FingerprintParts:
    norm = normalize_text(text)
    content_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    salary_key = f"{salary_from or ''}-{salary_to or ''}"
    contact_key = re.sub(r"\D", "", contact or "")
    base = "|".join(
        [
            normalize_text(title or "")[:80],
            normalize_text(company or "")[:80],
            salary_key,
            contact_key,
            content_hash[:16],
        ]
    )
    fingerprint = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return FingerprintParts(
        fingerprint=fingerprint,
        content_hash=content_hash,
        normalized_text=norm,
    )


def is_near_duplicate(
    left_title: str | None,
    left_company: str | None,
    left_text: str,
    right_title: str | None,
    right_company: str | None,
    right_text: str,
    *,
    threshold: int = 86,
) -> bool:
    """RapidFuzz near-duplicate check across sources."""
    left_company_n = normalize_text(left_company or "")
    right_company_n = normalize_text(right_company or "")
    company_similar = (
        bool(left_company_n)
        and bool(right_company_n)
        and fuzz.token_set_ratio(left_company_n, right_company_n) >= 90
    )
    title_score = fuzz.token_set_ratio(
        normalize_text(left_title or ""),
        normalize_text(right_title or ""),
    )
    text_score = fuzz.token_set_ratio(normalize_text(left_text), normalize_text(right_text))
    if company_similar and title_score >= 80:
        return True
    if company_similar and text_score >= threshold - 5:
        return True
    return bool(text_score >= threshold and title_score >= 70)

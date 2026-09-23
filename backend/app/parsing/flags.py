"""Suspicious / scam flag detection (dictionary-based)."""

from __future__ import annotations

import re
from typing import Any

from app.parsing.extract import ParsedVacancy

DEFAULT_SUSPICIOUS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PAYMENT_REQUIRED", re.compile(r"(?i)оплат[аы]\s+обучени|вложен|стартовый\s+взнос")),
    ("MLM_SUSPECTED", re.compile(r"(?i)млм|сетев(ой|ого)\s+маркетинг|пассивный\s+доход")),
    ("CASINO", re.compile(r"(?i)казино|букмекер")),
    ("CRYPTO", re.compile(r"(?i)крипт|nft|биткоин|форекс")),
    ("TOO_GOOD_SALARY", re.compile(r"(?i)от\s*10\s*000\s*в\s*день|доход\s*без\s*ограничений")),
    ("MASS_RECRUITMENT", re.compile(r"(?i)набор\s+сотрудников|срочно\s+требуется\s+\d{2,}")),
]


def detect_flags(
    text: str,
    parsed: ParsedVacancy,
    *,
    extra_keywords: list[str] | None = None,
) -> list[str]:
    flags: list[str] = []
    if not parsed.company_name:
        flags.append("NO_COMPANY")
    if parsed.salary_from is None and parsed.salary_to is None:
        flags.append("NO_SALARY")
    if not parsed.requirements and not parsed.duties and len(text) < 120:
        flags.append("NO_JOB_DESCRIPTION")
    if not parsed.contact:
        flags.append("SUSPICIOUS_CONTACT")

    for flag, pattern in DEFAULT_SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            flags.append(flag)

    if extra_keywords:
        lowered = text.lower()
        for kw in extra_keywords:
            if kw.lower() in lowered:
                flags.append("SUSPICIOUS_KEYWORD")
                break

    salary = parsed.salary_to or parsed.salary_from
    if salary and salary >= 250_000 and parsed.category in {"mass", "other", "hospitality"}:
        flags.append("TOO_GOOD_SALARY")

    # unique preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            ordered.append(f)
    return ordered


def flags_penalty(flags: list[str]) -> tuple[float, list[dict[str, Any]]]:
    """Return VQS penalty points and explanation entries."""
    weights = {
        "PAYMENT_REQUIRED": 40,
        "MLM_SUSPECTED": 35,
        "CASINO": 40,
        "CRYPTO": 25,
        "TOO_GOOD_SALARY": 20,
        "MASS_RECRUITMENT": 12,
        "NO_JOB_DESCRIPTION": 10,
        "NO_COMPANY": 5,
        "NO_SALARY": 3,
        "SUSPICIOUS_CONTACT": 4,
        "SUSPICIOUS_KEYWORD": 15,
    }
    penalty = 0.0
    reasons: list[dict[str, Any]] = []
    for flag in flags:
        pts = float(weights.get(flag, 5))
        penalty += pts
        reasons.append({"flag": flag, "penalty": pts})
    return min(penalty, 70.0), reasons

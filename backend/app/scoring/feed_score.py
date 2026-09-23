"""FeedScore — ranking for a media-style city job feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.parsing.extract import ParsedVacancy


@dataclass
class FeedScoreResult:
    score: float
    explanation: dict[str, Any]


def compute_feed_score(
    *,
    vqs: float,
    parsed: ParsedVacancy,
    flags: list[str],
    source_created_at: datetime | None,
    category_counts_today: dict[str, int],
    company_counts_today: dict[str, int],
    now: datetime | None = None,
) -> FeedScoreResult:
    """Score how worth showing this vacancy in the city media feed right now."""
    now = now or datetime.now(UTC)
    parts: dict[str, float] = {}
    reasons: list[str] = []

    # Base from VQS (0-40)
    parts["vqs"] = (vqs / 100.0) * 40.0
    reasons.append(f"VQS вклад {parts['vqs']:.1f}")

    # Freshness 0-15
    freshness, fresh_reason = _freshness(source_created_at, now)
    parts["freshness"] = freshness
    reasons.append(fresh_reason)

    # Interest / unusualness 0-15
    interest, interest_reason = _interest(parsed)
    parts["interest"] = interest
    reasons.append(interest_reason)

    # Career potential 0-10
    career, career_reason = _career(parsed)
    parts["career"] = career
    reasons.append(career_reason)

    # Company trust slice already partly in VQS; small boost 0-5
    company_boost = 5.0 if parsed.company_name else 1.5
    parts["company"] = company_boost

    # Accessibility / hire realism 0-5 (not only "no experience")
    access, access_reason = _hire_realism(parsed)
    parts["accessibility"] = access
    reasons.append(access_reason)

    # Penalties
    penalties: list[dict[str, Any]] = []
    penalty = 0.0

    category = parsed.category or "other"
    cat_count = category_counts_today.get(category, 0)
    if category == "mass" and cat_count >= 1:
        penalty += 12
        penalties.append({"type": "mass_category_repeat", "value": 12})
    elif cat_count >= 3:
        penalty += 10
        penalties.append({"type": "category_diversity", "value": 10, "category": category})
    elif cat_count >= 2:
        penalty += 5
        penalties.append({"type": "category_diversity", "value": 5, "category": category})

    company_key = (parsed.company_name or "").lower().strip()
    if company_key and company_counts_today.get(company_key, 0) >= 1:
        penalty += 8
        penalties.append({"type": "same_company", "value": 8})

    hard_flags = {"PAYMENT_REQUIRED", "MLM_SUSPECTED", "CASINO", "CRYPTO", "TOO_GOOD_SALARY"}
    for flag in flags:
        if flag in hard_flags:
            penalty += 15
            penalties.append({"type": "flag", "flag": flag, "value": 15})
        elif flag == "MASS_RECRUITMENT":
            penalty += 10
            penalties.append({"type": "flag", "flag": flag, "value": 10})
        elif flag == "NO_JOB_DESCRIPTION":
            penalty += 8
            penalties.append({"type": "flag", "flag": flag, "value": 8})

    total = max(0.0, min(100.0, sum(parts.values()) - penalty))
    return FeedScoreResult(
        score=round(total, 2),
        explanation={
            "parts": {k: round(v, 2) for k, v in parts.items()},
            "penalties": penalties,
            "reasons": reasons,
            "feed_score": round(total, 2),
        },
    )


def _freshness(created: datetime | None, now: datetime) -> tuple[float, str]:
    if created is None:
        return 6.0, "Дата неизвестна — средняя свежесть"
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    hours = (now - created.astimezone(UTC)).total_seconds() / 3600
    if hours < 2:
        return 15.0, "Свежесть < 2ч"
    if hours < 6:
        return 13.0, "Свежесть < 6ч"
    if hours < 24:
        return 11.0, "Свежесть < 24ч"
    if hours < 72:
        return 7.0, "Свежесть 1–3 дня"
    return 3.0, "Старше 3 дней"


def _interest(parsed: ParsedVacancy) -> tuple[float, str]:
    category = parsed.category or "other"
    base = {
        "it": 14,
        "engineering": 13,
        "medicine": 12,
        "education": 11,
        "marketing": 12,
        "office": 9,
        "sales": 7,
        "logistics": 6,
        "hospitality": 7,
        "mass": 3,
        "other": 7,
    }.get(category, 7)
    title = (parsed.title or "").lower()
    boost_kw = ("ведущий", "старший", "руководитель", "product", "аналитик", "архитектор")
    if any(k in title for k in boost_kw):
        base = min(15, base + 2)
        return float(base), f"Интересная роль ({category}) с сильным заголовком"
    return float(base), f"Интересность категории {category}"


def _career(parsed: ParsedVacancy) -> tuple[float, str]:
    category = parsed.category or "other"
    if category in {"it", "engineering", "medicine", "education", "marketing"}:
        return 9.0, "Высокий карьерный потенциал"
    if category in {"office", "sales"}:
        return 6.0, "Средний карьерный потенциал"
    if category == "mass":
        return 2.0, "Низкий карьерный потенциал"
    return 5.0, "Нейтральный карьерный потенциал"


def _hire_realism(parsed: ParsedVacancy) -> tuple[float, str]:
    exp = (parsed.experience_required or "").lower()
    if "без опыта" in exp:
        return 4.0, "Легко откликнуться"
    if "2" in exp or "3" in exp:
        return 5.0, "Реалистичный mid-level найм"
    if "5" in exp:
        return 3.0, "Узкий пул кандидатов"
    return 3.5, "Требования умеренно прозрачны"

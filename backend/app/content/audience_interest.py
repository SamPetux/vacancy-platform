"""AudienceInterestScore — how interesting a vacancy is for a career media audience."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.content.markers import MASS_CATEGORIES
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.availability import FieldAvailability, assess_availability

DEFAULT_AIS_WEIGHTS: dict[str, float] = {
    "novelty_role": 18,
    "employer_pull": 12,
    "conditions_edge": 16,
    "experience_value": 14,
    "career_potential": 12,
    "accessibility": 10,
    "task_interest": 10,
    "shareability": 8,
}


@dataclass
class AisComponent:
    name: str
    value: float
    max_value: float
    reason: str
    signals: list[str] = field(default_factory=list)


@dataclass
class AudienceInterestResult:
    total: float
    components: list[AisComponent]
    explanation: dict[str, Any]


def compute_audience_interest(
    vacancy: Vacancy,
    score: VacancyScore | None,
    *,
    availability: FieldAvailability | None = None,
    role_frequency: float | None = None,
    salary_percentile: float | None = None,
    weights: dict[str, float] | None = None,
) -> AudienceInterestResult:
    """Deterministic AIS from existing scores + optional cohort stats.

    role_frequency: share of similar roles in city cohort (0..1); None = unknown.
    salary_percentile: 0..100 within cohort; None = unknown.
    """
    w = {**DEFAULT_AIS_WEIGHTS, **(weights or {})}
    avail = availability or assess_availability(vacancy)
    comps = _components(score)
    category = (vacancy.category or "other").lower()

    parts = [
        _novelty(category, role_frequency, w["novelty_role"]),
        _employer(comps.get("company", 0), avail, w["employer_pull"]),
        _conditions(
            comps,
            avail,
            salary_percentile,
            w["conditions_edge"],
        ),
        _experience_value(comps.get("experience_value", 0), w["experience_value"]),
        _career(
            category,
            comps.get("experience_value", 0),
            vacancy.feed_score,
            w["career_potential"],
        ),
        _accessibility_comp(comps.get("accessibility", 0), avail, w["accessibility"]),
        _task_interest(avail, comps.get("experience_value", 0), w["task_interest"]),
        _shareability(
            avail,
            category,
            role_frequency,
            salary_percentile,
            w["shareability"],
        ),
    ]

    total = round(min(100.0, sum(p.value for p in parts)), 2)
    explanation = {
        "total": total,
        "components": {
            p.name: {
                "value": p.value,
                "max": p.max_value,
                "reason": p.reason,
                "signals": p.signals,
            }
            for p in parts
        },
        "inputs": {
            "role_frequency": role_frequency,
            "salary_percentile": salary_percentile,
            "category": category,
        },
    }
    return AudienceInterestResult(total=total, components=parts, explanation=explanation)


def _components(score: VacancyScore | None) -> dict[str, float]:
    if score is None:
        return {}
    return {
        "salary": float(score.salary or 0),
        "workload": float(score.workload or 0),
        "flexibility": float(score.flexibility or 0),
        "company": float(score.company or 0),
        "experience_value": float(score.experience_value or 0),
        "accessibility": float(score.accessibility or 0),
        "transparency": float(score.transparency or 0),
    }


def _novelty(
    category: str,
    role_frequency: float | None,
    max_v: float,
) -> AisComponent:
    signals: list[str] = []
    value = 0.0
    if role_frequency is not None:
        if role_frequency < 0.02:
            value = max_v
            signals.append("role_freq_lt_2pct")
        elif role_frequency < 0.05:
            value = max_v * 0.75
            signals.append("role_freq_lt_5pct")
        elif role_frequency < 0.10:
            value = max_v * 0.45
            signals.append("role_freq_lt_10pct")
        else:
            value = max_v * 0.15
            signals.append("role_common")
    elif category not in MASS_CATEGORIES:
        value = max_v * 0.55
        signals.append(f"category_{category}")
    else:
        value = max_v * 0.2
        signals.append("mass_or_common_category")
    return AisComponent(
        name="novelty_role",
        value=round(value, 2),
        max_value=max_v,
        reason="Необычность роли для городской ленты",
        signals=signals,
    )


def _employer(
    company_score: float,
    avail: FieldAvailability,
    max_v: float,
) -> AisComponent:
    signals: list[str] = []
    if not avail.has_company:
        return AisComponent(
            name="employer_pull",
            value=0.0,
            max_value=max_v,
            reason="Работодатель не указан",
            signals=["no_company"],
        )
    ratio = min(1.0, company_score / 15.0)
    value = max_v * ratio
    if company_score >= 11:
        signals.append("strong_company_score")
    else:
        signals.append("has_company")
    return AisComponent(
        name="employer_pull",
        value=round(value, 2),
        max_value=max_v,
        reason="Привлекательность работодателя по прозрачности и известности",
        signals=signals,
    )


def _conditions(
    comps: dict[str, float],
    avail: FieldAvailability,
    salary_percentile: float | None,
    max_v: float,
) -> AisComponent:
    signals: list[str] = []
    value = 0.0
    if salary_percentile is not None and avail.has_salary:
        if salary_percentile >= 75:
            value += max_v * 0.7
            signals.append("salary_p75_plus")
        elif salary_percentile >= 60:
            value += max_v * 0.45
            signals.append("salary_p60_plus")
        else:
            value += max_v * 0.2
            signals.append("salary_below_p60")
    elif avail.has_salary:
        value += max_v * 0.25 * min(1.0, comps.get("salary", 0) / 25.0)
        signals.append("salary_present_no_cohort")
    flex = comps.get("flexibility", 0)
    if flex >= 6:
        value += max_v * 0.3
        signals.append("flexibility_high")
    value = min(max_v, value)
    return AisComponent(
        name="conditions_edge",
        value=round(value, 2),
        max_value=max_v,
        reason="Конкурентоспособность условий",
        signals=signals,
    )


def _experience_value(ev: float, max_v: float) -> AisComponent:
    ratio = min(1.0, ev / 15.0)
    return AisComponent(
        name="experience_value",
        value=round(max_v * ratio, 2),
        max_value=max_v,
        reason="Полезность профессионального опыта",
        signals=["experience_value_component"] if ev else ["low_experience_value"],
    )


def _career(
    category: str,
    ev: float,
    feed_score: float | None,
    max_v: float,
) -> AisComponent:
    signals: list[str] = []
    value = 0.0
    career_cats = {"it", "engineering", "medicine", "marketing", "education"}
    if category in career_cats:
        value += max_v * 0.45
        signals.append(f"career_category_{category}")
    value += max_v * 0.35 * min(1.0, ev / 15.0)
    if feed_score and feed_score >= 50:
        value += max_v * 0.2
        signals.append("feed_score_ge_50")
    value = min(max_v, value)
    return AisComponent(
        name="career_potential",
        value=round(value, 2),
        max_value=max_v,
        reason="Карьерный потенциал роли",
        signals=signals or ["baseline"],
    )


def _accessibility_comp(
    acc: float,
    avail: FieldAvailability,
    max_v: float,
) -> AisComponent:
    signals: list[str] = []
    ratio = min(1.0, acc / 10.0)
    value = max_v * ratio
    if avail.experience_label == "без опыта":
        value = min(max_v, value + max_v * 0.15)
        signals.append("no_experience")
    signals.append("accessibility_component")
    return AisComponent(
        name="accessibility",
        value=round(value, 2),
        max_value=max_v,
        reason="Доступность трудоустройства",
        signals=signals,
    )


def _task_interest(
    avail: FieldAvailability,
    ev: float,
    max_v: float,
) -> AisComponent:
    signals: list[str] = []
    if not avail.has_duties:
        return AisComponent(
            name="task_interest",
            value=0.0,
            max_value=max_v,
            reason="Задачи не описаны достаточно подробно",
            signals=["no_duties"],
        )
    value = max_v * 0.55
    signals.append("has_duties")
    if ev >= 9:
        value = max_v
        signals.append("experience_value_ge_9")
    elif avail.has_skills:
        value = max_v * 0.75
        signals.append("has_skills")
    return AisComponent(
        name="task_interest",
        value=round(value, 2),
        max_value=max_v,
        reason="Интересность задач",
        signals=signals,
    )


def _shareability(
    avail: FieldAvailability,
    category: str,
    role_frequency: float | None,
    salary_percentile: float | None,
    max_v: float,
) -> AisComponent:
    signals: list[str] = []
    value = 0.0
    if avail.remote_label in {"удалённо", "гибрид"}:
        value += max_v * 0.35
        signals.append(avail.remote_label)
    if role_frequency is not None and role_frequency < 0.05:
        value += max_v * 0.35
        signals.append("rare_role")
    elif category not in MASS_CATEGORIES:
        value += max_v * 0.2
        signals.append("non_mass_category")
    if salary_percentile is not None and salary_percentile >= 75:
        value += max_v * 0.3
        signals.append("salary_notable")
    value = min(max_v, value)
    return AisComponent(
        name="shareability",
        value=round(value, 2),
        max_value=max_v,
        reason="Потенциал поделиться с знакомым",
        signals=signals or ["baseline"],
    )

"""Vacancy Quality Score (VQS) — deterministic and explainable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.parsing.extract import ParsedVacancy
from app.parsing.flags import detect_flags, flags_penalty

DEFAULT_WEIGHTS: dict[str, float] = {
    "salary": 25,
    "workload": 15,
    "flexibility": 10,
    "company": 15,
    "experience_value": 15,
    "accessibility": 10,
    "transparency": 10,
}


@dataclass
class ComponentScore:
    name: str
    value: float
    max_value: float
    reason: str
    signals: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)


@dataclass
class VqsResult:
    total: float
    components: list[ComponentScore]
    flags: list[str]
    explanation: dict[str, Any]


def compute_vqs(
    parsed: ParsedVacancy,
    raw_text: str,
    *,
    weights: dict[str, float] | None = None,
    known_company: bool = False,
) -> VqsResult:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    flags = detect_flags(raw_text, parsed)
    components = [
        _salary_score(parsed, w["salary"]),
        _workload_score(parsed, w["workload"]),
        _flexibility_score(parsed, w["flexibility"]),
        _company_score(parsed, w["company"], known_company=known_company),
        _experience_value_score(parsed, w["experience_value"]),
        _accessibility_score(parsed, w["accessibility"]),
        _transparency_score(parsed, w["transparency"]),
    ]
    total = sum(c.value for c in components)
    penalty, flag_reasons = flags_penalty(flags)
    total = max(0.0, min(100.0, total - penalty))

    explanation = {
        "components": [
            {
                "name": c.name,
                "value": round(c.value, 2),
                "max": c.max_value,
                "reason": c.reason,
                "signals": c.signals,
                "penalties": c.penalties,
            }
            for c in components
        ],
        "flags": flags,
        "flag_penalties": flag_reasons,
        "penalty_total": penalty,
        "vqs": round(total, 2),
    }
    return VqsResult(
        total=round(total, 2),
        components=components,
        flags=flags,
        explanation=explanation,
    )


def _salary_score(parsed: ParsedVacancy, max_v: float) -> ComponentScore:
    salary = parsed.salary_to or parsed.salary_from
    if salary is None:
        return ComponentScore(
            "salary",
            max_v * 0.35,
            max_v,
            "Зарплата не указана — мягкий штраф",
            [],
            ["missing_salary"],
        )
    # Relative bands for NN mixed market (not "higher is always better")
    if salary < 35_000:
        value, reason = max_v * 0.3, "Низкая зарплата относительно рынка"
    elif salary < 55_000:
        value, reason = max_v * 0.55, "Ниже медианы для многих ролей"
    elif salary < 90_000:
        value, reason = max_v * 0.8, "Адекватная зарплата"
    elif salary < 150_000:
        value, reason = max_v * 0.95, "Выше среднего — сильный сигнал"
    else:
        # Very high: good only with strong company/title; otherwise suspicious handled by flags
        value, reason = max_v * 0.7, "Очень высокая сумма — нужна осторожность"
    if parsed.salary_from and parsed.salary_to:
        value = min(max_v, value + max_v * 0.05)
        reason += "; указан диапазон"
    return ComponentScore("salary", round(value, 2), max_v, reason, [f"salary={salary}"], [])


def _workload_score(parsed: ParsedVacancy, max_v: float) -> ComponentScore:
    schedule = (parsed.schedule or "").lower()
    hours = parsed.hours_per_day
    if "вахта" in schedule:
        return ComponentScore(
            "workload",
            max_v * 0.35,
            max_v,
            "Вахта — высокая нагрузка",
            [schedule],
            ["shift_work"],
        )
    if schedule in {"5/2", "пятидневка"} or "5/2" in schedule:
        base = max_v * 0.9
        reason = "Стандартный график 5/2"
    elif schedule in {"2/2", "3/3"}:
        base = max_v * 0.65
        reason = f"Сменный график {schedule}"
    elif "6/1" in schedule:
        base = max_v * 0.4
        reason = "Плотный график 6/1"
    elif schedule:
        base = max_v * 0.7
        reason = f"График: {schedule}"
    else:
        base = max_v * 0.55
        reason = "График не указан — нейтрально"
    if hours is not None:
        if hours <= 8:
            base = min(max_v, base + max_v * 0.05)
        elif hours >= 12:
            base = max(0, base - max_v * 0.2)
            reason += f"; смена {hours}ч"
    return ComponentScore("workload", round(base, 2), max_v, reason, [], [])


def _flexibility_score(parsed: ParsedVacancy, max_v: float) -> ComponentScore:
    score = max_v * 0.5
    signals: list[str] = []
    if parsed.remote_type == "remote" or parsed.schedule == "удалённо":
        score = max_v * 0.9
        signals.append("remote")
    elif parsed.schedule == "гибкий":
        score = max_v * 0.8
        signals.append("flexible")
    elif parsed.schedule == "частичная":
        score = max_v * 0.75
        signals.append("part_time")
    if parsed.address:
        score = min(max_v, score + max_v * 0.1)
        signals.append("address")
    return ComponentScore("flexibility", round(score, 2), max_v, "Формат работы", signals, [])


def _company_score(parsed: ParsedVacancy, max_v: float, *, known_company: bool) -> ComponentScore:
    if not parsed.company_name:
        return ComponentScore(
            "company",
            max_v * 0.35,
            max_v,
            "Компания не указана",
            [],
            ["no_company"],
        )
    value = max_v * 0.65
    signals = [parsed.company_name]
    if known_company:
        value = max_v * 0.85
        signals.append("known_in_db")
    if any(x in parsed.company_name.lower() for x in ("ооо", "ао", "пао", "ип")):
        value = min(max_v, value + max_v * 0.05)
    return ComponentScore(
        "company",
        round(value, 2),
        max_v,
        "Прозрачность работодателя",
        signals,
        [],
    )


def _experience_value_score(parsed: ParsedVacancy, max_v: float) -> ComponentScore:
    category = parsed.category or "other"
    table = {
        "it": 0.95,
        "engineering": 0.9,
        "medicine": 0.85,
        "education": 0.8,
        "marketing": 0.8,
        "office": 0.7,
        "sales": 0.55,
        "logistics": 0.5,
        "hospitality": 0.45,
        "mass": 0.25,
        "other": 0.5,
    }
    ratio = table.get(category, 0.5)
    reason = f"Категория {category}: оценка полезности опыта"
    # Interesting mid-level roles get a boost
    exp = (parsed.experience_required or "").lower()
    if "2" in exp or "3" in exp or "1 год" in exp:
        ratio = min(1.0, ratio + 0.08)
        reason += "; есть карьерный вход с опытом"
    return ComponentScore(
        "experience_value",
        round(max_v * ratio, 2),
        max_v,
        reason,
        [category],
        [],
    )


def _accessibility_score(parsed: ParsedVacancy, max_v: float) -> ComponentScore:
    exp = (parsed.experience_required or "").lower()
    category = parsed.category or "other"
    if "без опыта" in exp or "noexperience" in exp.replace(" ", ""):
        # High accessibility but skilled roles shouldn't be crushed for requiring experience
        value = max_v * 0.9
        reason = "Доступно без опыта"
    elif "5" in exp:
        value = max_v * 0.35 if category in {"mass", "sales", "hospitality"} else max_v * 0.55
        reason = "Высокие требования к опыту"
    elif "2" in exp or "3" in exp:
        value = max_v * 0.7
        reason = "Умеренные требования (2–3 года) — нормально для качественных ролей"
    elif exp:
        value = max_v * 0.65
        reason = f"Требования: {parsed.experience_required}"
    else:
        value = max_v * 0.55
        reason = "Опыт не указан — нейтрально"
    return ComponentScore("accessibility", round(value, 2), max_v, reason, [], [])


def _transparency_score(parsed: ParsedVacancy, max_v: float) -> ComponentScore:
    checks = [
        ("salary", parsed.salary_from is not None or parsed.salary_to is not None),
        ("company", bool(parsed.company_name)),
        ("schedule", bool(parsed.schedule)),
        ("duties_or_req", bool(parsed.duties or parsed.requirements)),
        ("contact", bool(parsed.contact)),
        ("title", bool(parsed.title)),
    ]
    present = sum(1 for _, ok in checks if ok)
    ratio = present / len(checks)
    signals = [name for name, ok in checks if ok]
    return ComponentScore(
        "transparency",
        round(max_v * ratio, 2),
        max_v,
        f"Заполнено полей: {present}/{len(checks)}",
        signals,
        [],
    )

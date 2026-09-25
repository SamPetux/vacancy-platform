"""Editorial grade and label selection from VQS / FeedScore signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.availability import FieldAvailability
from app.publishing.models import EditorialRating

EDITORIAL_LABELS: tuple[str, ...] = (
    "выше рынка",
    "сильные условия",
    "сильный карьерный шаг",
    "хороший вход в профессию",
    "редкая позиция",
    "сильный бренд",
    "гибкий формат",
    "достойное предложение",
    "интересные задачи",
    "хороший баланс",
    "для опытных",
    "карьерный рост рядом",
    "стабильный работодатель",
    "практический опыт",
    "сильный стек",
    "удобная локация",
    "прозрачные условия",
    "сменный комфортный ритм",
    "массовый найм с плюсом",
    "узкая экспертиза",
    "перспективная позиция",
    "спокойный старт",
)


@dataclass(frozen=True)
class GradeResult:
    grade: str
    label: str
    reason: str


def assign_grade(
    *,
    vqs: float | None,
    feed_score: float | None,
) -> str:
    """A+ / A / B+ / B from VQS + FeedScore (published vacancies only)."""
    v = float(vqs or 0)
    f = float(feed_score or 0)
    if v >= 70 and f >= 55:
        return "A+"
    if v >= 64 and f >= 48:
        return "A"
    if v >= 58 and f >= 42:
        return "B+"
    return "B"


def build_editorial(
    vacancy: Vacancy,
    availability: FieldAvailability,
    score: VacancyScore | None,
    *,
    variant: int = 0,
) -> EditorialRating | None:
    vqs = vacancy.quality_score
    feed = vacancy.feed_score
    if vqs is None and feed is None:
        return None

    grade = assign_grade(vqs=vqs, feed_score=feed)
    label, reason = _pick_label_and_reason(
        vacancy,
        availability,
        score,
        grade=grade,
        variant=variant,
    )
    if not reason:
        return None
    return EditorialRating(grade=grade, label=label, reason=reason)


def _pick_label_and_reason(
    vacancy: Vacancy,
    availability: FieldAvailability,
    score: VacancyScore | None,
    *,
    grade: str,
    variant: int,
) -> tuple[str, str]:
    components = _components(score)
    category = (vacancy.category or "other").lower()
    candidates: list[tuple[int, str, str]] = []

    salary = components.get("salary", 0)
    flexibility = components.get("flexibility", 0)
    company = components.get("company", 0)
    experience_value = components.get("experience_value", 0)
    transparency = components.get("transparency", 0)
    workload = components.get("workload", 0)
    accessibility = components.get("accessibility", 0)

    if salary >= 20 and availability.has_salary:
        candidates.append(
            (
                90,
                "выше рынка",
                "По зарплате предложение заметно сильнее типичных похожих вакансий в городе.",
            )
        )
    if availability.has_benefits and (flexibility >= 6 or salary >= 18):
        candidates.append(
            (
                85,
                "сильные условия",
                "Хороший уровень условий и понятный пакет того, что предлагают кандидату.",
            )
        )
    if experience_value >= 12 and category in {
        "it",
        "engineering",
        "medicine",
        "marketing",
        "education",
    }:
        candidates.append(
            (
                84,
                "сильный карьерный шаг",
                "Роль заметно усиливает резюме: сильные задачи и карьерный потенциал.",
            )
        )
    if availability.experience_label == "без опыта" and (
        availability.has_duties or company >= 9
    ):
        candidates.append(
            (
                82,
                "хороший вход в профессию",
                "Прозрачный старт без требования многолетнего опыта.",
            )
        )
        candidates.append(
            (
                70,
                "спокойный старт",
                "Спокойный вход: понятные условия и реалистичные ожидания к кандидату.",
            )
        )
    if category in {"medicine", "engineering", "it"} and experience_value >= 10:
        candidates.append(
            (
                80,
                "узкая экспертиза",
                "Узкая специализация, которая редко встречается в городской ленте.",
            )
        )
    if company >= 11 and availability.has_company:
        candidates.append(
            (
                78,
                "сильный бренд",
                "Работодатель узнаваем, а условия описаны достаточно прозрачно.",
            )
        )
        candidates.append(
            (
                72,
                "стабильный работодатель",
                "Стабильный работодатель с понятной рамкой роли.",
            )
        )
    if availability.remote_label in {"удалённо", "гибрид"} or (
        availability.schedule_label and "гибк" in availability.schedule_label
    ):
        candidates.append(
            (
                77,
                "гибкий формат",
                "Формат работы даёт больше свободы, чем типичный офисный найм.",
            )
        )
    if availability.has_skills and category in {"it", "engineering", "marketing"}:
        candidates.append(
            (
                76,
                "сильный стек",
                "В вакансии явно указан рабочий стек — полезный сигнал для специалиста.",
            )
        )
    if availability.has_duties and experience_value >= 9:
        candidates.append(
            (
                74,
                "интересные задачи",
                "Задачи сформулированы конкретно и выглядят содержательно.",
            )
        )
    if workload >= 10 and flexibility >= 6:
        candidates.append(
            (
                73,
                "хороший баланс",
                "Сочетание нагрузки и гибкости выглядит сбалансированным.",
            )
        )
    if availability.experience_label in {"опыт 2+", "опыт 5+"}:
        candidates.append(
            (
                71,
                "для опытных",
                "Вакансия рассчитана на кандидата с уже набранным профильным опытом.",
            )
        )
    if availability.schedule_label in {"2/2", "3/3"} and salary >= 15:
        candidates.append(
            (
                69,
                "сменный комфортный ритм",
                "Сменный график с нормальной оплатой — понятный формат для города.",
            )
        )
    if category in {"mass", "sales", "hospitality"} and (
        salary >= 18 or availability.has_benefits
    ):
        candidates.append(
            (
                68,
                "массовый найм с плюсом",
                "Обычная роль, но по условиям заметно сильнее типичного массового найма.",
            )
        )
    if transparency >= 8:
        candidates.append(
            (
                66,
                "прозрачные условия",
                "Ключевые параметры вакансии заполнены без лишней туманности.",
            )
        )
    if availability.has_district or availability.has_address:
        candidates.append(
            (
                64,
                "удобная локация",
                "Место работы указано конкретно — проще оценить логистику.",
            )
        )
    if accessibility >= 8 and availability.experience_label == "без опыта":
        candidates.append(
            (
                63,
                "практический опыт",
                "Можно быстро получить практический опыт на понятных задачах.",
            )
        )
    if float(vacancy.feed_score or 0) >= 50 and experience_value >= 8:
        candidates.append(
            (
                62,
                "перспективная позиция",
                "Хорошее сочетание качества вакансии и полезности для городской ленты.",
            )
        )
    if grade in {"A+", "A"}:
        candidates.append(
            (
                55,
                "достойное предложение",
                "Сильное сочетание прозрачности, условий и карьерной ценности.",
            )
        )
    else:
        candidates.append(
            (
                40,
                "достойное предложение",
                "Аккуратное и достаточно прозрачное предложение для публикации.",
            )
        )
    if category not in {"mass", "sales", "other"}:
        candidates.append(
            (
                50,
                "редкая позиция",
                "Для городской ленты это более редкий и заметный профиль роли.",
            )
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    # variant rotates among top-3 distinct labels
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, label, reason in candidates:
        if label in seen:
            continue
        seen.add(label)
        unique.append((label, reason))
        if len(unique) >= 3:
            break
    if not unique:
        return "достойное предложение", "Вакансия прошла отбор и годится для публикации."
    chosen = unique[variant % len(unique)]
    return chosen


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


def explanation_signals(score: VacancyScore | None) -> list[str]:
    """Debug helper for tests / admin."""
    detail: dict[str, Any] = {}
    if score and isinstance(score.components_detail, dict):
        detail = score.components_detail
    return list(detail.keys())

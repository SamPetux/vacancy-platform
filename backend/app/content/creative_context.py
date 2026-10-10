"""CreativeContext — how to present a vacancy to the audience."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.content.markers import (
    CAREER_CATEGORIES,
    MARKERS,
    MASS_CATEGORIES,
    MarkerKey,
)
from app.content.visual.families import VisualFamily, default_layouts_for_family
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.availability import FieldAvailability, assess_availability
from app.publishing.grades import assign_grade


class CreativeContext(BaseModel):
    vacancy_id: UUID | None = None
    content_item_id: UUID | None = None
    creative_type: str
    primary_signal: str
    secondary_signal: str | None = None
    category: str
    visual_family: str
    layout_variant: str
    editorial_reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    data_grounds: list[str] = Field(default_factory=list)
    internal_grade: str | None = None
    audience_interest: float | None = None


def build_creative_context(
    vacancy: Vacancy,
    score: VacancyScore | None,
    *,
    availability: FieldAvailability | None = None,
    salary_percentile: float | None = None,
    salary_sample: int = 0,
    role_frequency: float | None = None,
    audience_interest: float | None = None,
    recent_markers: list[str] | None = None,
    recent_families: list[str] | None = None,
    preferred_family: VisualFamily | None = None,
    layout_variant: str | None = None,
) -> CreativeContext:
    """Pick evidence-backed marker + visual family. Does not mutate VQS/FeedScore."""
    avail = availability or assess_availability(vacancy)
    comps = _comps(score)
    category = (vacancy.category or "other").lower()
    grade = assign_grade(vqs=vacancy.quality_score, feed_score=vacancy.feed_score)

    candidates = _eligible_markers(
        vacancy,
        comps,
        avail,
        category=category,
        salary_percentile=salary_percentile,
        salary_sample=salary_sample,
        role_frequency=role_frequency,
    )
    if not candidates:
        candidates = [
            (
                MarkerKey.WORTH_NOTICING,
                0.45,
                "Вакансия прошла отбор и годится для публикации.",
                ["passed_thresholds"],
            )
        ]

    # Soft penalty for recently used markers
    recent_m = {m.upper() for m in (recent_markers or [])}
    ranked: list[tuple[float, MarkerKey, float, str, list[str]]] = []
    for key, conf, reason, grounds in candidates:
        penalty = 0.12 if key.value in recent_m else 0.0
        ranked.append((conf - penalty, key, conf, reason, grounds))
    ranked.sort(key=lambda x: (x[0], MARKERS[x[1]].priority), reverse=True)
    _, key, conf, reason, grounds = ranked[0]

    secondary = _secondary(ranked[1:], key)

    family = preferred_family or _pick_family(
        key,
        category,
        avail,
        recent_families=recent_families or [],
    )
    layouts = default_layouts_for_family(family)
    variant = layout_variant or layouts[0]

    marker = MARKERS[key]
    return CreativeContext(
        vacancy_id=vacancy.id,
        creative_type=key.value,
        primary_signal=marker.primary_signal,
        secondary_signal=secondary,
        category=category,
        visual_family=family.value,
        layout_variant=variant,
        editorial_reason=reason,
        confidence=round(min(1.0, max(0.0, conf)), 3),
        data_grounds=grounds,
        internal_grade=grade,
        audience_interest=audience_interest,
    )


def _comps(score: VacancyScore | None) -> dict[str, float]:
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


def _eligible_markers(
    vacancy: Vacancy,
    comps: dict[str, float],
    avail: FieldAvailability,
    *,
    category: str,
    salary_percentile: float | None,
    salary_sample: int,
    role_frequency: float | None,
) -> list[tuple[MarkerKey, float, str, list[str]]]:
    out: list[tuple[MarkerKey, float, str, list[str]]] = []
    vqs = float(vacancy.quality_score or 0)
    feed = float(vacancy.feed_score or 0)
    flags = {str(f) for f in (getattr(vacancy, "flags", None) or [])}

    if vqs >= 70 and feed >= 55 and comps.get("transparency", 0) >= 7:
        out.append(
            (
                MarkerKey.STRONG_OFFER,
                0.9,
                "Высокое общее качество предложения и понятное описание условий.",
                ["vqs_ge_70", "feed_ge_55", "transparency_ge_7"],
            )
        )

    # ABOVE_MARKET — requires cohort evidence, never salary component alone
    if (
        avail.has_salary
        and salary_percentile is not None
        and salary_sample >= 15
        and salary_percentile >= 75
    ):
        out.append(
            (
                MarkerKey.ABOVE_MARKET,
                0.94,
                f"Зарплата в верхнем квартиле сопоставимых вакансий "
                f"(выборка {salary_sample} за период).",
                ["salary_p75", f"sample_{salary_sample}"],
            )
        )

    if (
        comps.get("experience_value", 0) >= 12
        and category in CAREER_CATEGORIES
    ):
        out.append(
            (
                MarkerKey.CAREER_STEP,
                0.86,
                "Роль усиливает резюме: сильные задачи и карьерный потенциал.",
                ["experience_value_ge_12", f"category_{category}"],
            )
        )

    if avail.experience_label == "без опыта" and (
        avail.has_duties or comps.get("company", 0) >= 9
    ) and comps.get("accessibility", 0) >= 6:
        out.append(
            (
                MarkerKey.GOOD_START,
                0.85,
                "Низкий порог входа и понятные условия для старта.",
                ["no_experience", "accessibility_ge_6"],
            )
        )

    if role_frequency is not None and role_frequency < 0.02:
        out.append(
            (
                MarkerKey.RARE_ROLE,
                0.87,
                "Такая роль редко встречается в городской ленте.",
                ["role_freq_lt_2pct"],
            )
        )
    elif (
        role_frequency is not None
        and role_frequency < 0.05
        and category not in MASS_CATEGORIES
    ):
        out.append(
            (
                MarkerKey.RARE_ROLE,
                0.78,
                "Профиль роли заметно реже типичных массовых вакансий.",
                ["role_freq_lt_5pct", f"category_{category}"],
            )
        )

    salary_ok_p60 = (
        salary_percentile is not None
        and salary_sample >= 15
        and salary_percentile >= 60
    )
    if avail.has_benefits and (
        comps.get("flexibility", 0) >= 6 or salary_ok_p60
    ):
        grounds = ["has_benefits"]
        if comps.get("flexibility", 0) >= 6:
            grounds.append("flexibility_ge_6")
        if salary_ok_p60:
            grounds.append("salary_p60")
        out.append(
            (
                MarkerKey.STRONG_CONDITIONS,
                0.8,
                "Хороший уровень условий и понятный пакет для кандидата.",
                grounds,
            )
        )

    if avail.remote_label in {"удалённо", "гибрид"} or (
        avail.schedule_label and "гибк" in avail.schedule_label
    ):
        out.append(
            (
                MarkerKey.FLEX_FORMAT,
                0.83,
                "Формат работы даёт больше свободы, чем типичный офисный найм.",
                ["flex_or_remote"],
            )
        )

    if avail.has_duties and comps.get("experience_value", 0) >= 9:
        out.append(
            (
                MarkerKey.INTERESTING_WORK,
                0.79,
                "Задачи сформулированы конкретно и выглядят содержательно.",
                ["has_duties", "experience_value_ge_9"],
            )
        )

    if avail.experience_label == "без опыта":
        out.append(
            (
                MarkerKey.NO_EXPERIENCE,
                0.75,
                "Работодатель явно рассматривает кандидатов без опыта.",
                ["experience_label_no_experience"],
            )
        )

    if avail.experience_label in {"опыт 2+", "опыт 5+"}:
        out.append(
            (
                MarkerKey.FOR_SENIORS,
                0.74,
                "Вакансия рассчитана на кандидата с профильным опытом.",
                ["experience_2_plus"],
            )
        )

    if comps.get("workload", 0) >= 10 and comps.get("flexibility", 0) >= 6:
        out.append(
            (
                MarkerKey.GOOD_BALANCE,
                0.76,
                "Сочетание нагрузки и гибкости выглядит сбалансированным.",
                ["workload_ge_10", "flexibility_ge_6"],
            )
        )

    hard = {"PAYMENT_REQUIRED", "MLM_SUSPECTED", "CASINO"}
    if (
        comps.get("experience_value", 0) >= 8
        and feed >= 50
        and not (flags & hard)
    ):
        out.append(
            (
                MarkerKey.GROWTH_TRACK,
                0.72,
                "Хорошее сочетание качества роли и полезности для развития.",
                ["experience_value_ge_8", "feed_ge_50"],
            )
        )

    data_label = _data_point_label(avail)
    if data_label:
        out.append(
            (
                MarkerKey.DATA_POINT,
                0.7,
                f"В вакансии явно указано: {data_label}.",
                ["data_point", data_label],
            )
        )

    out.sort(key=lambda x: (x[1], MARKERS[x[0]].priority), reverse=True)
    return out


def _data_point_label(avail: FieldAvailability) -> str | None:
    if avail.schedule_label in {"2/2", "3/3", "5/2"}:
        return avail.schedule_label
    if avail.experience_label == "без опыта":
        return "0 лет опыта"
    return None


def _secondary(
    rest: list[tuple[float, MarkerKey, float, str, list[str]]],
    primary: MarkerKey,
) -> str | None:
    for _, key, _, _, _ in rest:
        if key == primary or key == MarkerKey.DATA_POINT:
            continue
        return MARKERS[key].primary_signal
    return None


def _pick_family(
    marker: MarkerKey,
    category: str,
    avail: FieldAvailability,
    *,
    recent_families: list[str],
) -> VisualFamily:
    recent_list = [f.upper() for f in recent_families]
    recent_set = set(recent_list)
    tail = recent_list[-2:]
    preferred: list[VisualFamily] = []
    if marker == MarkerKey.DATA_POINT and _data_point_label(avail):
        preferred.append(VisualFamily.RADAR_DATA)
    if marker in {MarkerKey.RARE_ROLE, MarkerKey.STRONG_OFFER, MarkerKey.CAREER_STEP}:
        preferred.append(VisualFamily.RADAR_TYPOGRAPHY)
    preferred.extend(
        [
            VisualFamily.RADAR_SIGNAL,
            VisualFamily.RADAR_ORBIT,
            VisualFamily.RADAR_CATEGORY,
            VisualFamily.RADAR_CITY,
        ]
    )
    # Category family slightly preferred for non-mass
    if category not in MASS_CATEGORIES:
        preferred.insert(1, VisualFamily.RADAR_CATEGORY)

    for fam in preferred:
        if fam.value not in tail:
            return fam
    for fam in preferred:
        if fam.value not in recent_set:
            return fam
    return preferred[0]

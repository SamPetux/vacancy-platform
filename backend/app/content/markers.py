"""Editorial marker dictionary — evidence-gated public signals."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MarkerKey(StrEnum):
    STRONG_OFFER = "STRONG_OFFER"
    ABOVE_MARKET = "ABOVE_MARKET"
    GOOD_START = "GOOD_START"
    CAREER_STEP = "CAREER_STEP"
    RARE_ROLE = "RARE_ROLE"
    STRONG_CONDITIONS = "STRONG_CONDITIONS"
    FLEX_FORMAT = "FLEX_FORMAT"
    INTERESTING_WORK = "INTERESTING_WORK"
    NO_EXPERIENCE = "NO_EXPERIENCE"
    FOR_SENIORS = "FOR_SENIORS"
    GOOD_BALANCE = "GOOD_BALANCE"
    GROWTH_TRACK = "GROWTH_TRACK"
    DATA_POINT = "DATA_POINT"
    WORTH_NOTICING = "WORTH_NOTICING"


@dataclass(frozen=True, slots=True)
class MarkerDef:
    key: MarkerKey
    label: str  # public UPPERCASE short label
    primary_signal: str  # human short phrase
    description: str
    priority: int  # higher = preferred when multiple match


MARKERS: dict[MarkerKey, MarkerDef] = {
    MarkerKey.STRONG_OFFER: MarkerDef(
        key=MarkerKey.STRONG_OFFER,
        label="СИЛЬНАЯ ВАКАНСИЯ",
        primary_signal="Сильная вакансия",
        description="Высокое общее качество и прозрачность предложения",
        priority=95,
    ),
    MarkerKey.ABOVE_MARKET: MarkerDef(
        key=MarkerKey.ABOVE_MARKET,
        label="ВЫШЕ РЫНКА",
        primary_signal="Выше рынка",
        description="Зарплата ≥ P75 сопоставимой выборки города",
        priority=96,  # preferred over STRONG_OFFER when cohort evidence exists
    ),
    MarkerKey.CAREER_STEP: MarkerDef(
        key=MarkerKey.CAREER_STEP,
        label="КАРЬЕРНЫЙ ШАГ",
        primary_signal="Карьерный шаг",
        description="Высокий карьерный потенциал роли",
        priority=88,
    ),
    MarkerKey.GOOD_START: MarkerDef(
        key=MarkerKey.GOOD_START,
        label="ХОРОШИЙ СТАРТ",
        primary_signal="Хороший старт",
        description="Доступный вход и полезный опыт",
        priority=86,
    ),
    MarkerKey.RARE_ROLE: MarkerDef(
        key=MarkerKey.RARE_ROLE,
        label="РЕДКАЯ РОЛЬ",
        primary_signal="Редкая роль",
        description="Необычная или редкая профессия в городе",
        priority=84,
    ),
    MarkerKey.STRONG_CONDITIONS: MarkerDef(
        key=MarkerKey.STRONG_CONDITIONS,
        label="СИЛЬНЫЕ УСЛОВИЯ",
        primary_signal="Сильные условия",
        description="Выгодное сочетание условий и бенефитов",
        priority=82,
    ),
    MarkerKey.FLEX_FORMAT: MarkerDef(
        key=MarkerKey.FLEX_FORMAT,
        label="ГИБКИЙ ФОРМАТ",
        primary_signal="Гибкий формат",
        description="Удалёнка, гибрид или гибкий график",
        priority=80,
    ),
    MarkerKey.INTERESTING_WORK: MarkerDef(
        key=MarkerKey.INTERESTING_WORK,
        label="ИНТЕРЕСНЫЙ ОПЫТ",
        primary_signal="Интересный опыт",
        description="Конкретные содержательные задачи",
        priority=78,
    ),
    MarkerKey.NO_EXPERIENCE: MarkerDef(
        key=MarkerKey.NO_EXPERIENCE,
        label="БЕЗ ОПЫТА",
        primary_signal="Без опыта",
        description="Работодатель явно рассматривает новичков",
        priority=76,
    ),
    MarkerKey.FOR_SENIORS: MarkerDef(
        key=MarkerKey.FOR_SENIORS,
        label="ДЛЯ ОПЫТНЫХ",
        primary_signal="Для опытных",
        description="Квалифицированная позиция с опытом 2+",
        priority=74,
    ),
    MarkerKey.GOOD_BALANCE: MarkerDef(
        key=MarkerKey.GOOD_BALANCE,
        label="ХОРОШИЙ БАЛАНС",
        primary_signal="Хороший баланс",
        description="Сочетание нагрузки, гибкости и оплаты",
        priority=72,
    ),
    MarkerKey.GROWTH_TRACK: MarkerDef(
        key=MarkerKey.GROWTH_TRACK,
        label="ПЕРСПЕКТИВНАЯ ПОЗИЦИЯ",
        primary_signal="Перспективная позиция",
        description="Подтверждённый потенциал развития",
        priority=70,
    ),
    MarkerKey.DATA_POINT: MarkerDef(
        key=MarkerKey.DATA_POINT,
        label="ФАКТ",
        primary_signal="Подтверждённый факт",
        description="Числовое преимущество из вакансии (график, опыт)",
        priority=65,
    ),
    MarkerKey.WORTH_NOTICING: MarkerDef(
        key=MarkerKey.WORTH_NOTICING,
        label="СТОИТ ЗАМЕТИТЬ",
        primary_signal="Стоит заметить",
        description="Fallback: прошла отбор, сильный маркер недоступен",
        priority=40,
    ),
}

# Categories with career-growth bias for CAREER_STEP.
CAREER_CATEGORIES: frozenset[str] = frozenset(
    {"it", "engineering", "medicine", "marketing", "education"}
)

# Mass categories excluded from soft rarity.
MASS_CATEGORIES: frozenset[str] = frozenset({"mass", "sales", "other", "hospitality"})


def marker_label(key: str | MarkerKey) -> str:
    mk = MarkerKey(key) if isinstance(key, str) else key
    return MARKERS[mk].label


def all_marker_options() -> list[dict[str, str]]:
    return [
        {
            "key": m.key.value,
            "label": m.label,
            "primary_signal": m.primary_signal,
            "description": m.description,
        }
        for m in sorted(MARKERS.values(), key=lambda x: -x.priority)
    ]

"""Vacancy detection from free-form posts (Level 1: keywords/rules)."""

from __future__ import annotations

import re

VACANCY_POSITIVE = re.compile(
    r"(?i)("
    r"ваканси[яи]|ищем|требуется|требуются|нужен|нужна|нужны|"
    r"открыта\s+вакансия|приглашаем\s+(на\s+работу|в\s+команду)|"
    r"зарплата|з\/п|з\.\s*п|оклад|график\s*работы|условия\s+работы|"
    r"отклик|резюме|трудоустрой"
    r")"
)

VACANCY_NEGATIVE = re.compile(
    r"(?i)("
    r"резюме\s+соискателя|ищу\s+работу|рассмотрю\s+предложения|"
    r"сниму|сдам|прода[мю]|куплю|отдам\s+даром|розыгрыш|конкурс"
    r")"
)


def is_vacancy_text(text: str | None, *, structured_hint: bool = False) -> bool:
    """Return True when text likely describes a job opening."""
    if structured_hint:
        return True
    if not text or len(text.strip()) < 40:
        return False
    cleaned = text.strip()
    if VACANCY_NEGATIVE.search(cleaned) and not VACANCY_POSITIVE.search(cleaned):
        return False
    return VACANCY_POSITIVE.search(cleaned) is not None

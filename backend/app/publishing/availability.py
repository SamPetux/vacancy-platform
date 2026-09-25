"""Deterministic availability of vacancy fields for the template engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.vacancy import Vacancy
from app.parsing.sections import is_stub_requirements
from app.publishing.salary import format_salary_line


@dataclass(frozen=True)
class FieldAvailability:
    has_title: bool
    has_company: bool
    has_salary: bool
    salary_line: str | None
    has_schedule: bool
    has_remote: bool
    has_experience: bool
    has_duties: bool
    has_requirements: bool
    has_benefits: bool
    has_address: bool
    has_district: bool
    has_skills: bool
    skills: list[str]
    schedule_interesting: bool
    remote_label: str | None
    experience_label: str | None
    schedule_label: str | None


_BORING_SCHEDULES = {
    "полный рабочий день",
    "полная занятость",
    "полный день",
}


def assess_availability(
    vacancy: Vacancy,
    *,
    skills: list[str] | None = None,
) -> FieldAvailability:
    skills = skills or []
    salary_line = format_salary_line(
        vacancy.salary_from,
        vacancy.salary_to,
        currency=vacancy.salary_currency,
    )
    remote_label = _remote_label(vacancy.remote_type, vacancy.schedule)
    schedule_label = _schedule_label(vacancy.schedule, remote_label)
    experience_label = _experience_label(vacancy.experience_required)
    duties_ok = bool(vacancy.duties and len(vacancy.duties.strip()) >= 40)
    req_ok = bool(
        vacancy.requirements
        and not is_stub_requirements(vacancy.requirements)
        and len(vacancy.requirements.strip()) >= 30
    )
    benefits_ok = bool(vacancy.benefits and len(vacancy.benefits.strip()) >= 30)
    schedule_interesting = bool(
        schedule_label
        and schedule_label.lower() not in _BORING_SCHEDULES
        and schedule_label != remote_label
    )
    return FieldAvailability(
        has_title=bool(vacancy.title and vacancy.title.strip()),
        has_company=bool(vacancy.company_name and vacancy.company_name.strip()),
        has_salary=salary_line is not None,
        salary_line=salary_line,
        has_schedule=bool(vacancy.schedule),
        has_remote=remote_label is not None,
        has_experience=experience_label is not None,
        has_duties=duties_ok,
        has_requirements=req_ok,
        has_benefits=benefits_ok,
        has_address=bool(vacancy.address),
        has_district=bool(vacancy.district),
        has_skills=len(skills) >= 2,
        skills=skills,
        schedule_interesting=schedule_interesting,
        remote_label=remote_label,
        experience_label=experience_label,
        schedule_label=schedule_label,
    )


def _remote_label(remote_type: str | None, schedule: str | None) -> str | None:
    remote = (remote_type or "").lower()
    sched = (schedule or "").lower()
    if remote in {"remote", "удалённо", "удаленно"} or "удал" in sched:
        return "удалённо"
    if remote in {"hybrid", "гибрид"} or "гибрид" in sched:
        return "гибрид"
    if remote in {"office", "офис"}:
        return "офис"
    return None


def _schedule_label(schedule: str | None, remote_label: str | None) -> str | None:
    if not schedule:
        return None
    raw = schedule.strip()
    lowered = raw.lower()
    mapping = {
        "5/2": "5/2",
        "2/2": "2/2",
        "3/3": "3/3",
        "6/1": "6/1",
        "вахта": "вахта",
        "вахтовый метод": "вахта",
        "гибкий": "гибкий график",
        "режим гибкого рабочего времени": "гибкий график",
        "удалённо": "удалённо",
        "частичная": "частичная занятость",
        "неполный рабочий день/неполная рабочая неделя": "частичная занятость",
        "неполный рабочий день": "частичная занятость",
        "частичная занятость / совместительство": "частичная занятость",
        "сменная работа": "сменный график",
        "сменный график работы": "сменный график",
        "полный рабочий день": "полный день",
    }
    for key, label in mapping.items():
        if key in lowered:
            if label == remote_label:
                return None
            return label
    if lowered in _BORING_SCHEDULES:
        return "полный день"
    return raw[:40]


def _experience_label(experience: str | None) -> str | None:
    if not experience:
        return None
    lowered = experience.strip().lower()
    if "без опыта" in lowered or "не имеет значения" in lowered:
        return "без опыта"
    if "1" in lowered and ("год" in lowered or "лет" in lowered or "года" in lowered):
        return "опыт 1+"
    if "2" in lowered or "3" in lowered:
        return "опыт 2+"
    if "5" in lowered or "4" in lowered or "6" in lowered:
        return "опыт 5+"
    return f"опыт: {experience.strip()[:24]}"

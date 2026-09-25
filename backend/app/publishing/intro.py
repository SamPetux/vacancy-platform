"""Deterministic editorial intro (1–3 sentences) from vacancy facts."""

from __future__ import annotations

from app.models.vacancy import Vacancy
from app.publishing.availability import FieldAvailability
from app.publishing.textutil import extract_bullets, prose_summary


def build_intro(
    vacancy: Vacancy,
    availability: FieldAvailability,
    *,
    city_name: str,
    variant: int = 0,
) -> str:
    title = (vacancy.title or "Вакансия").strip()
    company = (vacancy.company_name or "").strip()
    category = (vacancy.category or "other").lower()

    what = _what_sentence(title, company, category, variant)
    task_hint = _task_hint(vacancy, availability)
    why = _why_sentence(availability, category, city_name, variant)

    parts = [what]
    if task_hint:
        parts.append(task_hint)
    if why and why not in parts[0]:
        parts.append(why)
    # Keep 1–3 sentences
    return " ".join(parts[:3])


def _what_sentence(title: str, company: str, category: str, variant: int) -> str:
    role = _clean_title(title)
    templates_with_company = [
        f"Новая позиция «{role}» в {company}.",
        f"Открыта роль {role} — {company}.",
        f"{role} в компании {company}.",
    ]
    templates_no_company = [
        f"Открыта позиция «{role}».",
        f"В подборку добавлена вакансия: {role}.",
        f"Ищут специалиста на роль {role}.",
    ]
    if company:
        return templates_with_company[variant % len(templates_with_company)]
    _ = category
    return templates_no_company[variant % len(templates_no_company)]


def _task_hint(vacancy: Vacancy, availability: FieldAvailability) -> str | None:
    if availability.has_duties and vacancy.duties:
        bullets = extract_bullets(vacancy.duties, limit=2, max_len=70)
        if bullets:
            joined = " и ".join(b[0].lower() + b[1:] if b else b for b in bullets[:2])
            return f"В работе: {joined}."
        summary = prose_summary(vacancy.duties, max_len=140)
        if summary:
            return f"Основной фокус — {summary[0].lower() + summary[1:]}."
    if availability.has_requirements and vacancy.requirements:
        summary = prose_summary(vacancy.requirements, max_len=120)
        if summary:
            return f"Ориентир по профилю: {summary[0].lower() + summary[1:]}."
    return None


def _why_sentence(
    availability: FieldAvailability,
    category: str,
    city_name: str,
    variant: int,
) -> str:
    options: list[str] = []
    if availability.has_salary:
        options.append("Прозрачная зарплатная вилка упрощает сравнение с рынком.")
    if availability.remote_label == "удалённо":
        options.append("Формат удалённой работы удобен, если важна гибкость.")
    elif availability.remote_label == "гибрид":
        options.append("Гибридный формат — компромисс между офисом и удалёнкой.")
    if availability.experience_label == "без опыта":
        options.append("Подходит как спокойный вход без требования большого стажа.")
    elif availability.experience_label in {"опыт 1+", "опыт 2+"}:
        options.append(
            "Хороший вариант для тех, кто уже набрал базовый опыт и хочет двигаться дальше."
        )
    if category in {"it", "engineering", "medicine", "marketing"}:
        options.append("Роль даёт заметный карьерный след в профильной специализации.")
    if not options:
        options.append(f"Вакансия из подборки {city_name} с достаточной прозрачностью условий.")
    return options[variant % len(options)]


def _clean_title(title: str) -> str:
    cleaned = title.strip()
    cleaned = cleaned.removeprefix("Требуется ").removeprefix("требуется ")
    cleaned = cleaned.removeprefix("Вакансия: ").removeprefix("вакансия: ")
    # Strip emoji / decoration noise from VK titles
    cleaned = "".join(ch for ch in cleaned if ch.isprintable())
    return cleaned.strip(" ·|-—")[:120] or title[:120]

"""Build meta line and dynamic content blocks."""

from __future__ import annotations

from app.models.vacancy import Vacancy
from app.publishing.availability import FieldAvailability
from app.publishing.models import ContentBlock, TemplateMode
from app.publishing.textutil import extract_bullets, prose_summary


def build_meta(
    vacancy: Vacancy,
    availability: FieldAvailability,
    *,
    city_name: str,
    max_items: int = 4,
) -> list[str]:
    items: list[str] = []

    def add(value: str | None) -> None:
        if value and value not in items and len(items) < max_items:
            items.append(value)

    # Prefer district over city when present
    if availability.has_district and vacancy.district:
        add(vacancy.district.strip())
    else:
        add(city_name)

    add(availability.remote_label)
    if availability.schedule_interesting:
        add(availability.schedule_label)
    add(availability.experience_label)

    # Fill remaining slots with useful extras
    if len(items) < max_items and vacancy.employment_type:
        add(vacancy.employment_type.strip()[:40])
    if len(items) < max_items and availability.has_address and not availability.has_district:
        # Don't dump full street address into meta — too long
        pass
    return items[:max_items]


def build_blocks(
    vacancy: Vacancy,
    availability: FieldAvailability,
    *,
    mode: TemplateMode,
    variant: int = 0,
) -> list[ContentBlock]:
    max_blocks = {
        TemplateMode.COMPACT: 1,
        TemplateMode.STANDARD: 2,
        TemplateMode.EXTENDED: 3,
    }[mode]

    candidates: list[tuple[int, ContentBlock]] = []

    if availability.has_duties:
        items = extract_bullets(vacancy.duties, limit=4)
        if items:
            candidates.append(
                (100, ContentBlock(type="responsibilities", title="Задачи", items=items))
            )

    if availability.has_requirements:
        items = extract_bullets(vacancy.requirements, limit=4)
        if len(items) >= 2:
            candidates.append(
                (90, ContentBlock(type="requirements", title="Кого ищут", items=items))
            )
        else:
            text = prose_summary(vacancy.requirements, max_len=220)
            if text:
                candidates.append(
                    (
                        88,
                        ContentBlock(type="requirements", title="Кого ищут", text=text),
                    )
                )

    if availability.has_benefits:
        items = extract_bullets(vacancy.benefits, limit=4)
        # Avoid repeating salary/location already shown above
        items = [
            i
            for i in items
            if not _repeats_salary_or_location(i) and not _is_weak_offer(i)
        ]
        if items:
            candidates.append(
                (80, ContentBlock(type="offer", title="Что предлагают", items=items))
            )

    if availability.has_skills:
        stack_title = "Стек" if (vacancy.category or "") == "it" else "В работе"
        candidates.append(
            (
                70,
                ContentBlock(
                    type="stack",
                    title=stack_title,
                    text=" · ".join(availability.skills),
                ),
            )
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    # Slight order variation for regenerate without changing facts
    ordered = [block for _, block in candidates]
    if variant and len(ordered) > 1:
        pivot = variant % len(ordered)
        ordered = ordered[pivot:] + ordered[:pivot]
    return ordered[:max_blocks]


def choose_mode(availability: FieldAvailability, *, grade: str | None) -> TemplateMode:
    rich = sum(
        [
            availability.has_duties,
            availability.has_requirements,
            availability.has_benefits,
            availability.has_skills,
        ]
    )
    if grade in {"A+", "A"} and rich >= 3:
        return TemplateMode.EXTENDED
    if rich <= 1 and not availability.has_duties:
        return TemplateMode.COMPACT
    return TemplateMode.STANDARD


def _repeats_salary_or_location(item: str) -> bool:
    lowered = item.lower()
    return any(
        token in lowered
        for token in ("тыс", "зарплат", "оклад", "нижегород", "руб", "₽")
    )


def _is_weak_offer(item: str) -> bool:
    lowered = item.lower()
    weak = (
        "полная занятость",
        "совместительство",
        "полный рабочий день",
        "официальное трудоустройство",
    )
    return any(token in lowered for token in weak) and len(lowered) < 60

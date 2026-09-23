"""Rule-based vacancy field extraction (Level 1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedVacancy:
    title: str | None = None
    company_name: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_currency: str | None = "RUB"
    salary_period: str | None = None
    schedule: str | None = None
    hours_per_day: float | None = None
    experience_required: str | None = None
    remote_type: str | None = None
    address: str | None = None
    contact: str | None = None
    contact_type: str | None = None
    requirements: str | None = None
    duties: str | None = None
    category: str | None = None
    professional_role: str | None = None
    clean_text: str | None = None
    signals: dict[str, Any] = field(default_factory=dict)


_SALARY_RE = re.compile(
    r"(?i)(?:з[./]?п|зарплата|оклад|доход|оплата)?\s*[:=]?\s*"
    r"(?:от\s*)?(\d{2,3}(?:[\s\u00a0]?\d{3})+|\d{4,6})"
    r"(?:\s*[-–—]\s*(?:до\s*)?(\d{2,3}(?:[\s\u00a0]?\d{3})+|\d{4,6}))?"
    r"\s*(?:₽|руб\.?|р\b)"
)

_PHONE_RE = re.compile(
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
)

_SCHEDULE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b5\s*/\s*2\b|пятидневк|пн\s*[-–]\s*пт"), "5/2"),
    (re.compile(r"(?i)\b2\s*/\s*2\b"), "2/2"),
    (re.compile(r"(?i)\b3\s*/\s*3\b"), "3/3"),
    (re.compile(r"(?i)\b6\s*/\s*1\b"), "6/1"),
    (re.compile(r"(?i)вахт"), "вахта"),
    (re.compile(r"(?i)гибк(ий|ий\s+график)|свободн(ый|ый\s+график)"), "гибкий"),
    (re.compile(r"(?i)частичн(ая|ой)\s+занятост"), "частичная"),
    (re.compile(r"(?i)удал[её]нн|дистанционн|\bremote\b|из\s+дома"), "удалённо"),
]

_HOURS_RE = re.compile(r"(?i)(\d{1,2})\s*(?:час|ч\b)")

_EXPERIENCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)без\s+опыта|опыт\s+не\s+требуется|обуч(им|ение)"), "без опыта"),
    (re.compile(r"(?i)опыт\s*(?:от\s*)?1\s*год"), "от 1 года"),
    (re.compile(r"(?i)опыт\s*(?:от\s*)?2\s*[-–]?\s*3\s*лет|опыт\s*(?:от\s*)?3\s*лет"), "2–3 года"),
    (re.compile(r"(?i)опыт\s*(?:от\s*)?5\s*лет"), "от 5 лет"),
]

_COMPANY_RE = re.compile(
    r"(?i)(?:компани[яи]|работодатель)\s*[«\"']?([^\n«\"']{2,60})"
    r"|((?:ООО|АО|ПАО|ЗАО|ИП)\s+[«\"']?[\w\s\-«»\"]{2,60})"
)

_TITLE_LINE_RE = re.compile(
    r"(?i)^(?:вакансия[:\s]+)?(.{4,80}?)(?:\n|$)"
)

_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    # mass first — avoid mislabeling warehouse/courier as IT/office
    ("mass", (
        "курьер", "грузчик", "дворник", "уборщиц", "вахта", "комплектовщик",
        "сборщик заказ", "расклейщик", "промоутер", "упаковщик",
    )),
    ("it", (
        "разработчик", "программист", "devops", "тестировщик", "frontend",
        "backend", "python", "java", "1с разработ", "системный администратор",
    )),
    ("office", ("менеджер", "администратор", "ассистент", "секретар", "офис", "контролер")),
    ("sales", ("продаж", "продавец", "консультант", "торговый", "кассир")),
    ("marketing", ("маркетолог", "smm", "дизайнер", "контент")),
    ("medicine", ("врач", "медсестра", "фармацевт", "стоматолог", "ветеринар")),
    ("education", ("учитель", "преподаватель", "воспитатель", "репетитор", "педагог")),
    ("engineering", ("инженер", "технолог", "конструктор", "автомеханик", "автослесар")),
    ("logistics", ("логист", "кладовщик", "водитель", "экспедитор")),
    ("hospitality", ("повар", "пекарь", "барист", "официант", "хостес", "бургер")),
]


def parse_vacancy_text(
    text: str,
    *,
    structured: dict[str, Any] | None = None,
) -> ParsedVacancy:
    """Extract fields from free text, optionally merging structured source data."""
    clean = re.sub(r"\s+", " ", text).strip()
    result = ParsedVacancy(clean_text=clean)

    if structured:
        _apply_structured(result, structured)

    if not result.title:
        m = _TITLE_LINE_RE.search(text.strip())
        if m:
            candidate = m.group(1).strip(" .:—-")
            if len(candidate) >= 4:
                result.title = candidate[:120]

    if not result.company_name:
        m = _COMPANY_RE.search(text)
        if m:
            result.company_name = (m.group(1) or m.group(2) or "").strip(" .,—-«»\"'")[:120]

    if result.salary_from is None and result.salary_to is None:
        sm = _SALARY_RE.search(text)
        if sm:
            result.salary_from = _to_int(sm.group(1))
            result.salary_to = _to_int(sm.group(2)) if sm.group(2) else None
            result.salary_currency = "RUB"

    if not result.schedule:
        for pattern, label in _SCHEDULE_PATTERNS:
            if pattern.search(text):
                result.schedule = label
                if label == "удалённо":
                    result.remote_type = "remote"
                break

    if result.hours_per_day is None:
        hm = _HOURS_RE.search(text)
        if hm:
            hours = float(hm.group(1))
            if 3 <= hours <= 16:
                result.hours_per_day = hours

    if not result.experience_required:
        for pattern, label in _EXPERIENCE_PATTERNS:
            if pattern.search(text):
                result.experience_required = label
                break

    if not result.address:
        addr_m = re.search(r"(?im)^адрес\s*[:\-]\s*(.+)$", text)
        if addr_m:
            result.address = addr_m.group(1).strip()[:512]
        else:
            place_m = re.search(r"(?im)^место\s+работы\s*[:\-]\s*(.+)$", text)
            if place_m:
                place_val = place_m.group(1).strip()
                if not re.match(r"(?i)^не\s+имеет\s+значения", place_val):
                    result.address = place_val[:512]

    if not result.contact:
        pm = _PHONE_RE.search(text)
        if pm:
            result.contact = pm.group(0)
            result.contact_type = "phone"
        elif re.search(r"(?i)t\.me/|telegram|@\w{4,}", text):
            result.contact_type = "telegram"
            tm = re.search(r"(?i)(?:t\.me/\w+|@\w{4,})", text)
            result.contact = tm.group(0) if tm else "telegram"

    if not result.category and result.title:
        result.category = _guess_category(result.title + " " + clean)
        result.professional_role = result.title

    # Requirements / duties heuristics
    req_m = re.search(r"(?i)требования[:\s]+(.{20,400}?)(?:\n\n|обязанност|условия|$)", text)
    if req_m:
        result.requirements = req_m.group(1).strip()
    duty_m = re.search(r"(?i)обязанност\w*[:\s]+(.{20,400}?)(?:\n\n|требования|условия|$)", text)
    if duty_m:
        result.duties = duty_m.group(1).strip()

    result.signals = {
        "has_salary": result.salary_from is not None or result.salary_to is not None,
        "has_company": bool(result.company_name),
        "has_schedule": bool(result.schedule),
        "has_contact": bool(result.contact),
        "category": result.category,
    }
    return result


def _apply_structured(result: ParsedVacancy, data: dict[str, Any]) -> None:
    if data.get("name"):
        result.title = str(data["name"])
    employer = data.get("employer") or {}
    if isinstance(employer, dict) and employer.get("name"):
        result.company_name = str(employer["name"])
    salary = data.get("salary") or {}
    if isinstance(salary, dict):
        if salary.get("from") is not None:
            result.salary_from = int(salary["from"])
        if salary.get("to") is not None:
            result.salary_to = int(salary["to"])
        currency = salary.get("currency")
        if currency:
            result.salary_currency = "RUB" if currency in {"RUR", "RUB"} else str(currency)
    experience = data.get("experience") or {}
    if isinstance(experience, dict) and experience.get("name"):
        result.experience_required = str(experience["name"])
    schedule = data.get("schedule") or {}
    if isinstance(schedule, dict) and schedule.get("name"):
        schedule_name = str(schedule["name"])
        result.schedule = schedule_name
        if re.search(r"(?i)удал[её]нн|дистанционн|\bremote\b", schedule_name):
            result.remote_type = "remote"
    place = data.get("place_of_work")
    place_title = None
    if isinstance(place, dict):
        place_title = place.get("title") or place.get("name")
    elif isinstance(place, str):
        place_title = place
    if place_title:
        place_str = str(place_title)
        if re.search(r"(?i)удал[её]нн|дистанционн|\bremote\b|из\s+дома", place_str):
            result.remote_type = "remote"
            if not result.schedule:
                result.schedule = "удалённо"
    if data.get("address"):
        result.address = str(data["address"])[:512]
    roles = data.get("professional_roles") or []
    if roles and isinstance(roles, list) and isinstance(roles[0], dict):
        result.professional_role = str(roles[0].get("name") or "")
        result.category = _guess_category(result.professional_role or result.title or "")
    snippet = data.get("snippet") or {}
    if isinstance(snippet, dict):
        if snippet.get("requirement"):
            result.requirements = str(snippet["requirement"])
        if snippet.get("responsibility"):
            result.duties = str(snippet["responsibility"])


def _to_int(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    value = int(digits)
    return value if 5_000 <= value <= 1_000_000 else value


def _guess_category(text: str) -> str:
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(k in lowered for k in keywords):
            return category
    return "other"

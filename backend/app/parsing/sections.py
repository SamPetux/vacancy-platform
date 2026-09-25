"""Split mixed vacancy description blobs into duties / requirements / benefits."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SplitSections:
    duties: str | None = None
    requirements: str | None = None
    benefits: str | None = None


_SECTION_HEADERS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?im)^(?:\s*[►▶•\-–—*]?\s*)?"
            r"(?:обязанност\w*|задач[аи]|что\s+делать|чем\s+предстоит\s+заниматься|"
            r"функционал|должностные\s+обязанности)\s*[:\-–—]?\s*$"
        ),
        "duties",
    ),
    (
        re.compile(
            r"(?im)^(?:\s*[►▶•\-–—*]?\s*)?"
            r"(?:требования|кого\s+ищем|ожидания|наш\s+кандидат|"
            r"необходим\w*|нужен\s+опыт|квалификация)\s*[:\-–—]?\s*$"
        ),
        "requirements",
    ),
    (
        re.compile(
            r"(?im)^(?:\s*[►▶•\-–—*]?\s*)?"
            r"(?:мы\s+предлагаем|условия|что\s+предлагаем|что\s+даём|что\s+даем|"
            r"от\s+нас|бонусы|льгот\w*|преимущества)\s*[:\-–—]?\s*$"
        ),
        "benefits",
    ),
]

_INLINE_SECTION = re.compile(
    r"(?i)(?:^|\n)\s*(?:обязанност\w*|задач[аи]|требования|мы\s+предлагаем|"
    r"условия|что\s+предлагаем|от\s+нас)\s*[:\-–—]\s*"
)


def split_description_sections(text: str | None) -> SplitSections:
    """Split employer blob that mixes duties/requirements/benefits under headers."""
    if not text or not text.strip():
        return SplitSections()

    normalized = text.replace("\r\n", "\n").strip()
    lines = normalized.split("\n")
    buckets: dict[str, list[str]] = {"duties": [], "requirements": [], "benefits": []}
    current: str | None = None
    preamble: list[str] = []

    for line in lines:
        header = _match_header(line)
        if header is not None:
            current = header
            continue
        if current is None:
            preamble.append(line)
        else:
            buckets[current].append(line)

    # Inline "Обязанности: ..." style without line break after colon
    if not any(buckets.values()) and _INLINE_SECTION.search(normalized):
        return _split_inline(normalized)

    duties = _join(buckets["duties"])
    requirements = _join(buckets["requirements"])
    benefits = _join(buckets["benefits"])

    # If headers were missing but preamble looks like a bullet list of duties
    if duties is None and requirements is None and benefits is None and preamble:
        joined = _join(preamble)
        if joined and _looks_like_bullet_list(joined):
            duties = joined

    return SplitSections(duties=duties, requirements=requirements, benefits=benefits)


def merge_sections(
    *,
    duties: str | None,
    requirements: str | None,
    benefits: str | None,
    blob: str | None,
) -> SplitSections:
    """Prefer existing structured fields; fill gaps from splitting a mixed blob."""
    # SuperJob often stores the whole candidat blob in requirements
    from_requirements = split_description_sections(requirements)
    if from_requirements.duties or from_requirements.benefits:
        duties = duties or from_requirements.duties
        benefits = benefits or from_requirements.benefits
        if from_requirements.requirements:
            requirements = from_requirements.requirements

    split = split_description_sections(blob)
    return SplitSections(
        duties=duties or split.duties,
        requirements=_prefer_substantive(requirements, split.requirements),
        benefits=benefits or split.benefits,
    )


def is_stub_requirements(text: str | None) -> bool:
    """True for thin TrudVsem-style stubs that should not become a content block."""
    if not text:
        return True
    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    if len(cleaned) < 25:
        return True
    stub_prefixes = (
        "опыт:",
        "образование:",
        "опыт: без опыта",
        "опыт: от",
    )
    if cleaned.startswith(stub_prefixes) and len(cleaned) < 90:
        return True
    return cleaned.count(";") <= 1 and "опыт:" in cleaned and "образован" in cleaned


def _match_header(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return None
    for pattern, name in _SECTION_HEADERS:
        if pattern.match(stripped):
            return name
    return None


def _split_inline(text: str) -> SplitSections:
    parts = re.split(
        r"(?i)(?:^|\n)\s*(обязанност\w*|задач[аи]|требования|мы\s+предлагаем|"
        r"условия|что\s+предлагаем|от\s+нас)\s*[:\-–—]\s*",
        text,
    )
    if len(parts) < 3:
        return SplitSections()
    buckets: dict[str, list[str]] = {"duties": [], "requirements": [], "benefits": []}
    # parts: [preamble, header1, body1, header2, body2, ...]
    for i in range(1, len(parts) - 1, 2):
        header = parts[i].lower()
        body = parts[i + 1].strip()
        key = _header_key(header)
        if key and body:
            buckets[key].append(body)
    return SplitSections(
        duties=_join(buckets["duties"]),
        requirements=_join(buckets["requirements"]),
        benefits=_join(buckets["benefits"]),
    )


def _header_key(header: str) -> str | None:
    if header.startswith(("обязан", "задач")):
        return "duties"
    if header.startswith("требован"):
        return "requirements"
    if header.startswith(("мы предлага", "услови", "что предлага", "от нас")):
        return "benefits"
    return None


def _join(lines: list[str]) -> str | None:
    text = "\n".join(line.rstrip() for line in lines).strip()
    return text or None


def _looks_like_bullet_list(text: str) -> bool:
    bullets = re.findall(r"(?m)^\s*[•\-–—●▪]\s+\S+", text)
    return len(bullets) >= 2


def _prefer_substantive(primary: str | None, fallback: str | None) -> str | None:
    if primary and not is_stub_requirements(primary):
        return primary
    if fallback and not is_stub_requirements(fallback):
        return fallback
    return primary or fallback

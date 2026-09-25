"""Extract skill / stack tokens from vacancy text (deterministic dictionary)."""

from __future__ import annotations

import re

from app.models.vacancy import Vacancy

_SKILL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bpython\b"), "Python"),
    (re.compile(r"(?i)\bpostgresql\b|\bpostgres\b"), "PostgreSQL"),
    (re.compile(r"(?i)\bairflow\b"), "Airflow"),
    (re.compile(r"(?i)\bdocker\b"), "Docker"),
    (re.compile(r"(?i)\bkubernetes\b|\bk8s\b"), "Kubernetes"),
    (re.compile(r"(?i)\breact\b"), "React"),
    (re.compile(r"(?i)\btypescript\b"), "TypeScript"),
    (re.compile(r"(?i)\bjavascript\b|\bjs\b"), "JavaScript"),
    (re.compile(r"(?i)\bjava\b"), "Java"),
    (re.compile(r"(?i)\b1[cс]\b|\b1с\b"), "1С"),
    (re.compile(r"(?i)\bsql\b"), "SQL"),
    (re.compile(r"(?i)\bexcel\b"), "Excel"),
    (re.compile(r"(?i)\bautocad\b"), "AutoCAD"),
    (re.compile(r"(?i)\bcatia\b"), "CATIA"),
    (re.compile(r"(?i)\bsolidworks\b"), "SolidWorks"),
    (re.compile(r"(?i)\bfigma\b"), "Figma"),
    (re.compile(r"(?i)\bpower\s*bi\b"), "Power BI"),
    (re.compile(r"(?i)\btableau\b"), "Tableau"),
    (re.compile(r"(?i)\blinux\b"), "Linux"),
    (re.compile(r"(?i)\bgit\b"), "Git"),
    (re.compile(r"(?i)\bfastapi\b"), "FastAPI"),
    (re.compile(r"(?i)\bdjango\b"), "Django"),
    (re.compile(r"(?i)\bredis\b"), "Redis"),
    (re.compile(r"(?i)\bkafka\b"), "Kafka"),
]


def extract_skills(vacancy: Vacancy) -> list[str]:
    text = " ".join(
        part
        for part in (
            vacancy.title,
            vacancy.duties,
            vacancy.requirements,
            vacancy.clean_text,
            vacancy.raw_text,
        )
        if part
    )
    found: list[str] = []
    seen: set[str] = set()
    for pattern, label in _SKILL_PATTERNS:
        if pattern.search(text) and label not in seen:
            seen.add(label)
            found.append(label)
        if len(found) >= 6:
            break
    return found

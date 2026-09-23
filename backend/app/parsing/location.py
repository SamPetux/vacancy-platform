"""Deterministic work-location filter (city config driven, not hard-coded)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

OUT_OF_CITY_FLAG = "OUT_OF_CITY"

_REMOTE_RE = re.compile(
    r"(?i)удал[её]нн(?:ая|ой|о|ый|ые|ых)?\s+(?:работ|формат|занят|сотруд)|"
    r"(?:работ|формат|занят)\w*\s+удал[её]нн|"
    r"дистанционн(?:ая|ой|о|ый|ые)\s+(?:работ|формат|занят)|"
    r"(?:работ|формат)\w*\s+дистанционн|"
    r"\bremote\b|"
    r"работа\s+из\s+дома|"
    r"работа\s+на\s+дому|"
    r"home\s*office"
)
_UNSPECIFIED_RE = re.compile(
    r"(?i)^(?:не\s+имеет\s+значения|не\s+указан[оа]?|любой|anywhere|-)$"
)
_ADDRESS_LINE_RE = re.compile(
    r"(?im)^(?:адрес|место\s+работы)\s*[:\-]\s*(.+)$"
)
_WORK_IN_RE = re.compile(
    r"(?i)(?:место(?:м)?\s+работы|работа(?:ть|ем)?)\s+(?:в|на)\s+"
    r"([А-ЯЁA-Z][^.\n!?]{2,80})"
)
_SETTLEMENT_RE = re.compile(
    r"(?i)(?:пос[её]лок|пгт|село|деревня|аул|станица|хутор|"
    r"город(?:\s+типа)?|г\.)\s*"
    r"([А-ЯЁA-Z][А-Яа-яЁёA-Za-z\-]{1,40})"
)
_HIRE_FROM_RE = re.compile(
    r"(?i)(?:ищем\s+кандидат|кандидат\w*\s+из|набор\s+из|"
    r"из\s*:\s*|из\s+город|приглашаем\s+из)"
)
_COUNTRY_WORK_RE = re.compile(
    r"(?i)(?:в|на)\s+(?:египт\w*|турци\w*|кита\w*|оаэ|дуба\w*|"
    r"казахстан\w*|беларус\w*|армени\w*)|"
    r"\(\s*(?:египет|турция|кита[йя]|оаэ|дубай)\s*\)"
)


@dataclass(frozen=True)
class LocationPolicy:
    """Per-city location policy — aliases come from City configuration."""

    city_name: str
    region_name: str | None = None
    aliases: tuple[str, ...] = ()
    allow_remote: bool = True
    allow_unspecified: bool = True


@dataclass(frozen=True)
class LocationVerdict:
    allowed: bool
    is_remote: bool
    work_location: str | None
    reason: str
    flag: str | None = None


def build_location_policy(
    *,
    city_name: str,
    region_name: str | None = None,
    aliases: list[str] | None = None,
    allow_remote: bool = True,
    allow_unspecified: bool = True,
) -> LocationPolicy:
    """Build a policy from City fields without hard-coding a city name."""
    base = [city_name, *(aliases or [])]
    normalized = tuple(dict.fromkeys(_normalize(a) for a in base if a and _normalize(a)))
    return LocationPolicy(
        city_name=city_name,
        region_name=region_name,
        aliases=normalized,
        allow_remote=allow_remote,
        allow_unspecified=allow_unspecified,
    )


def evaluate_work_location(
    *,
    text: str,
    policy: LocationPolicy,
    address: str | None = None,
    remote_type: str | None = None,
    schedule: str | None = None,
    structured: dict[str, Any] | None = None,
) -> LocationVerdict:
    """Allow only local work location or (optionally) remote roles."""
    work_location = _extract_work_location(text=text, address=address, structured=structured)
    is_remote = _detect_remote(
        text=text,
        remote_type=remote_type,
        schedule=schedule,
        structured=structured,
    )

    # Explicit workplace address wins over weak/sticky remote signals.
    if work_location and not _UNSPECIFIED_RE.match(work_location.strip()):
        if _is_local(work_location, policy):
            return LocationVerdict(
                allowed=True,
                is_remote=False,
                work_location=work_location,
                reason="local_work_location",
            )
        if is_remote and policy.allow_remote and _explicit_remote_place(
            remote_type=remote_type,
            schedule=schedule,
            structured=structured,
        ):
            return LocationVerdict(
                allowed=True,
                is_remote=True,
                work_location=work_location,
                reason="remote_with_foreign_base",
            )
        return LocationVerdict(
            allowed=False,
            is_remote=False,
            work_location=work_location,
            reason="non_local_work_location",
            flag=OUT_OF_CITY_FLAG,
        )

    if is_remote and policy.allow_remote:
        return LocationVerdict(
            allowed=True,
            is_remote=True,
            work_location=work_location,
            reason="remote_allowed",
        )

    if work_location is None or _UNSPECIFIED_RE.match((work_location or "").strip()):
        if policy.allow_unspecified:
            return LocationVerdict(
                allowed=True,
                is_remote=False,
                work_location=work_location,
                reason="location_unspecified",
            )
        return LocationVerdict(
            allowed=False,
            is_remote=False,
            work_location=work_location,
            reason="location_missing",
            flag=OUT_OF_CITY_FLAG,
        )

    return LocationVerdict(
        allowed=False,
        is_remote=False,
        work_location=work_location,
        reason="non_local_work_location",
        flag=OUT_OF_CITY_FLAG,
    )


def _explicit_remote_place(
    *,
    remote_type: str | None,
    schedule: str | None,
    structured: dict[str, Any] | None,
) -> bool:
    """Strong remote signals only — ignores sticky remote_type alone."""
    del remote_type  # sticky DB value must not override concrete address
    if schedule and _REMOTE_RE.search(schedule):
        return True
    place = _structured_place(structured)
    return bool(place and _REMOTE_RE.search(place))


def _detect_remote(
    *,
    text: str,
    remote_type: str | None,
    schedule: str | None,
    structured: dict[str, Any] | None,
) -> bool:
    if (remote_type or "").lower() in {"remote", "удалённо", "удаленно"}:
        return True
    if schedule and _REMOTE_RE.search(schedule):
        return True
    place = _structured_place(structured)
    if place and _REMOTE_RE.search(place):
        return True
    return bool(_REMOTE_RE.search(text or ""))


def _extract_work_location(
    *,
    text: str,
    address: str | None,
    structured: dict[str, Any] | None,
) -> str | None:
    candidates: list[str] = []
    if address and str(address).strip():
        candidates.append(str(address).strip())

    structured_address = None
    if structured:
        if structured.get("address"):
            structured_address = str(structured["address"]).strip()
            if structured_address:
                candidates.append(structured_address)
        place = _structured_place(structured)
        if place and not _UNSPECIFIED_RE.match(place.strip()):
            candidates.append(place.strip())

    for match in _ADDRESS_LINE_RE.finditer(text or ""):
        value = match.group(1).strip()
        if value and not _UNSPECIFIED_RE.match(value):
            candidates.append(value)

    for match in _WORK_IN_RE.finditer(text or ""):
        value = match.group(1).strip(" .,—-")
        if value:
            candidates.append(value)

    for match in _COUNTRY_WORK_RE.finditer(text or ""):
        candidates.append(match.group(0).strip())

    # Settlement mentions outside hire-from lines are treated as work place.
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or _HIRE_FROM_RE.search(stripped):
            continue
        for _match in _SETTLEMENT_RE.finditer(stripped):
            candidates.append(stripped)
            break

    # Prefer the most specific non-hire line: last concrete address often is work place.
    for candidate in reversed(candidates):
        if candidate and not _HIRE_FROM_RE.search(candidate):
            return candidate[:240]
    return candidates[0][:240] if candidates else None


def _structured_place(structured: dict[str, Any] | None) -> str | None:
    if not structured:
        return None
    place = structured.get("place_of_work")
    if isinstance(place, dict):
        title = place.get("title") or place.get("name")
        return str(title) if title else None
    if isinstance(place, str) and place.strip():
        return place.strip()
    return None


def _is_local(location: str, policy: LocationPolicy) -> bool:
    norm = _normalize(location)
    if not norm:
        return False
    return any(alias and alias in norm for alias in policy.aliases)


def _normalize(value: str) -> str:
    text = value.lower().replace("ё", "е")
    text = re.sub(r"[«»\"']", " ", text)
    text = re.sub(r"[^\w\s\-./]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text

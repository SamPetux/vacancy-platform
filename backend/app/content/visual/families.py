"""Visual family catalog and layout variants (data-driven)."""

from __future__ import annotations

from enum import StrEnum


class VisualFamily(StrEnum):
    RADAR_SIGNAL = "RADAR_SIGNAL"
    RADAR_TYPOGRAPHY = "RADAR_TYPOGRAPHY"
    RADAR_ORBIT = "RADAR_ORBIT"
    RADAR_CATEGORY = "RADAR_CATEGORY"
    RADAR_DATA = "RADAR_DATA"
    RADAR_CITY = "RADAR_CITY"
    # Future (inactive)
    PHOTO_WORK = "PHOTO_WORK"
    PHOTO_PEOPLE = "PHOTO_PEOPLE"
    PHOTO_DETAIL = "PHOTO_DETAIL"
    BRAND_COMPANY = "BRAND_COMPANY"


ACTIVE_FAMILIES: tuple[VisualFamily, ...] = (
    VisualFamily.RADAR_SIGNAL,
    VisualFamily.RADAR_TYPOGRAPHY,
    VisualFamily.RADAR_ORBIT,
    VisualFamily.RADAR_CATEGORY,
    VisualFamily.RADAR_DATA,
    VisualFamily.RADAR_CITY,
)

# Layout variants per family — parameterized, not one Python file each.
_LAYOUTS: dict[VisualFamily, tuple[str, ...]] = {
    VisualFamily.RADAR_SIGNAL: ("signal_01", "signal_02", "signal_03"),
    VisualFamily.RADAR_TYPOGRAPHY: ("typo_01", "typo_02", "typo_03"),
    VisualFamily.RADAR_ORBIT: ("orbit_01", "orbit_02"),
    VisualFamily.RADAR_CATEGORY: ("category_01", "category_02"),
    VisualFamily.RADAR_DATA: ("data_01", "data_02"),
    VisualFamily.RADAR_CITY: ("city_01", "city_02"),
}

CATEGORY_ACCENTS: dict[str, str] = {
    "it": "#5B7C99",  # muted blue
    "engineering": "#6E7378",  # steel gray
    "office": "#4A5A6A",  # deep blue-gray
    "finance": "#4A5A6A",
    "marketing": "#7A5F73",  # muted plum
    "medicine": "#6B7F71",  # sage
    "education": "#6B7F71",
    "hospitality": "#A67C52",  # warm ochre
    "sales": "#A67C52",
    "logistics": "#6E7378",
    "mass": "#8B8983",
    "other": "#8B8983",
}


def default_layouts_for_family(family: VisualFamily) -> list[str]:
    return list(_LAYOUTS.get(family, ("signal_01",)))


def category_accent(category: str | None) -> str:
    return CATEGORY_ACCENTS.get((category or "other").lower(), "#8B8983")


def is_active_family(family: str | VisualFamily) -> bool:
    try:
        fam = VisualFamily(family) if isinstance(family, str) else family
    except ValueError:
        return False
    return fam in ACTIVE_FAMILIES

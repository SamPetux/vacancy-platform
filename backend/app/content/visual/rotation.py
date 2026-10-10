"""Visual Rotation — deterministic diversity penalties for feed visuals."""

from __future__ import annotations

from dataclasses import dataclass

from app.content.markers import MarkerKey
from app.content.visual.families import (
    ACTIVE_FAMILIES,
    VisualFamily,
    category_accent,
    default_layouts_for_family,
    is_active_family,
)


@dataclass(frozen=True, slots=True)
class VisualChoice:
    family: VisualFamily
    layout_variant: str
    accent: str
    marker_key: str
    score: float


@dataclass(frozen=True, slots=True)
class RecentVisual:
    family: str
    layout_variant: str
    marker_key: str
    category: str
    accent: str


def select_visual(
    *,
    marker_key: str,
    category: str,
    preferred_family: str | None = None,
    preferred_layout: str | None = None,
    recent: list[RecentVisual] | None = None,
    data_point_available: bool = False,
) -> VisualChoice:
    """Pick family+layout with penalties; reproducible given same recent window."""
    recent = recent or []
    category = (category or "other").lower()
    accent = category_accent(category)

    candidates: list[VisualFamily] = []
    if preferred_family and is_active_family(preferred_family):
        candidates.append(VisualFamily(preferred_family))
    if marker_key == MarkerKey.DATA_POINT.value and data_point_available:
        candidates.append(VisualFamily.RADAR_DATA)
    for fam in ACTIVE_FAMILIES:
        if fam == VisualFamily.RADAR_DATA and not data_point_available:
            continue
        if fam not in candidates:
            candidates.append(fam)

    best: VisualChoice | None = None
    for fam in candidates:
        layouts = default_layouts_for_family(fam)
        for layout in layouts:
            if preferred_layout and layout != preferred_layout and preferred_family == fam.value:
                # Still evaluate preferred layout first via score boost
                pass
            score = _score_candidate(
                fam,
                layout,
                marker_key=marker_key,
                category=category,
                accent=accent,
                recent=recent,
                preferred_family=preferred_family,
                preferred_layout=preferred_layout,
            )
            choice = VisualChoice(
                family=fam,
                layout_variant=layout,
                accent=accent,
                marker_key=marker_key,
                score=score,
            )
            if best is None or choice.score > best.score:
                best = choice

    assert best is not None
    return best


def _score_candidate(
    family: VisualFamily,
    layout: str,
    *,
    marker_key: str,
    category: str,
    accent: str,
    recent: list[RecentVisual],
    preferred_family: str | None,
    preferred_layout: str | None,
) -> float:
    score = 1.0
    if preferred_family == family.value:
        score += 0.35
    if preferred_layout == layout:
        score += 0.25

    # Look at last 5
    window = recent[-5:]
    for i, prev in enumerate(reversed(window)):
        weight = 1.0 - i * 0.15
        if prev.family == family.value:
            score -= 0.55 * weight
        if prev.layout_variant == layout:
            score -= 0.35 * weight
        if prev.marker_key == marker_key:
            score -= 0.4 * weight
        if prev.accent == accent:
            score -= 0.2 * weight
        if prev.category == category:
            score -= 0.1 * weight

    # Avoid identical last post
    if window and window[-1].family == family.value and window[-1].layout_variant == layout:
        score -= 1.0

    if family == VisualFamily.RADAR_DATA and marker_key != MarkerKey.DATA_POINT.value:
        score -= 2.0

    return round(score, 4)

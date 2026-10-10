"""Internal letter grades from VQS + FeedScore (not shown publicly by default)."""

from __future__ import annotations


def assign_grade(
    *,
    vqs: float | None,
    feed_score: float | None,
) -> str:
    """A+ / A / B+ / B from VQS + FeedScore (internal only)."""
    v = float(vqs or 0)
    f = float(feed_score or 0)
    if v >= 70 and f >= 55:
        return "A+"
    if v >= 64 and f >= 48:
        return "A"
    if v >= 58 and f >= 42:
        return "B+"
    return "B"

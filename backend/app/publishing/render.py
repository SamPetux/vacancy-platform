"""Render PostDraft into VK-ready plain text."""

from __future__ import annotations

from app.publishing.models import PostDraft


def render_post(draft: PostDraft) -> str:
    lines: list[str] = []

    if draft.company:
        lines.append(f"{draft.title} — {draft.company}")
    else:
        lines.append(draft.title)

    if draft.salary:
        lines.append(draft.salary)

    lines.append("")
    lines.append(draft.intro)

    if draft.meta:
        lines.append("")
        lines.append("· " + " · ".join(draft.meta))

    for block in draft.blocks:
        lines.append("")
        lines.append(f"► {block.title}:")
        if block.items:
            for item in block.items:
                lines.append(f"— {item}")
        elif block.text:
            lines.append(block.text)

    if draft.editorial:
        lines.append("")
        lines.append(f"▷ {draft.editorial.grade} / {draft.editorial.label}")
        lines.append(draft.editorial.reason)

    lines.append("")
    lines.append("Открыть вакансию —")
    if draft.source_url:
        lines.append(draft.source_url)

    text = "\n".join(lines).strip() + "\n"
    if len(text) > 1500:
        text = _trim_to_limit(draft, limit=1500)
    return text


def _trim_to_limit(draft: PostDraft, *, limit: int) -> str:
    """Drop weakest blocks first, then shorten intro."""
    trimmed = draft.model_copy(deep=True)
    while trimmed.blocks and len(render_post_raw(trimmed)) > limit:
        trimmed.blocks.pop()
    text = render_post_raw(trimmed)
    if len(text) <= limit:
        return text
    # Last resort: compress intro
    if len(trimmed.intro) > 120:
        trimmed.intro = trimmed.intro[:117].rsplit(" ", 1)[0] + "…"
    return render_post_raw(trimmed)[:limit]


def render_post_raw(draft: PostDraft) -> str:
    """Render without recursive trim (internal)."""
    lines: list[str] = []
    if draft.company:
        lines.append(f"{draft.title} — {draft.company}")
    else:
        lines.append(draft.title)
    if draft.salary:
        lines.append(draft.salary)
    lines.append("")
    lines.append(draft.intro)
    if draft.meta:
        lines.append("")
        lines.append("· " + " · ".join(draft.meta))
    for block in draft.blocks:
        lines.append("")
        lines.append(f"► {block.title}:")
        if block.items:
            for item in block.items:
                lines.append(f"— {item}")
        elif block.text:
            lines.append(block.text)
    if draft.editorial:
        lines.append("")
        lines.append(f"▷ {draft.editorial.grade} / {draft.editorial.label}")
        lines.append(draft.editorial.reason)
    lines.append("")
    lines.append("Открыть вакансию —")
    if draft.source_url:
        lines.append(draft.source_url)
    return "\n".join(lines).strip() + "\n"

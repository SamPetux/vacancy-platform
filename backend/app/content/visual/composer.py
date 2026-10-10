"""Parameterized PNG composer for Radar visual families (Pillow)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.content.visual.families import VisualFamily, category_accent

# Brand tokens (must stay aligned with admin CSS variables).
RADAR_CREAM = "#F2EFE8"
RADAR_PAPER = "#FAF9F6"
RADAR_BLACK = "#171717"
RADAR_GRAY = "#8B8983"
RADAR_ORANGE = "#FF6748"

DEFAULT_SIZE = (1080, 1080)


@dataclass(frozen=True, slots=True)
class BrandColors:
    cream: str = RADAR_CREAM
    paper: str = RADAR_PAPER
    black: str = RADAR_BLACK
    gray: str = RADAR_GRAY
    orange: str = RADAR_ORANGE


@dataclass(frozen=True, slots=True)
class ComposeRequest:
    marker_label: str
    visual_family: str
    layout_variant: str
    category: str
    secondary_signal: str | None = None
    data_point: str | None = None
    city_label: str | None = None
    accent: str | None = None
    size: tuple[int, int] = DEFAULT_SIZE


def compose_card(req: ComposeRequest, *, output_path: Path | None = None) -> Image.Image:
    """Render a brand card. Does not put title/company/salary on the image."""
    colors = BrandColors()
    accent = req.accent or category_accent(req.category)
    family = req.visual_family
    w, h = req.size
    img = Image.new("RGB", (w, h), colors.cream)
    draw = ImageDraw.Draw(img)

    if family == VisualFamily.RADAR_SIGNAL.value:
        _draw_signal(draw, w, h, req, colors, accent)
    elif family == VisualFamily.RADAR_TYPOGRAPHY.value:
        _draw_typography(draw, w, h, req, colors, accent)
    elif family == VisualFamily.RADAR_ORBIT.value:
        _draw_orbit(draw, w, h, req, colors, accent)
    elif family == VisualFamily.RADAR_CATEGORY.value:
        _draw_category(draw, w, h, req, colors, accent)
    elif family == VisualFamily.RADAR_DATA.value:
        _draw_data(draw, w, h, req, colors, accent)
    elif family == VisualFamily.RADAR_CITY.value:
        _draw_city(draw, w, h, req, colors, accent)
    else:
        _draw_signal(draw, w, h, req, colors, accent)

    _draw_footer(draw, w, h, colors)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format="PNG", optimize=True)
    return img


def _font(size: int, *, bold: bool = False) -> Any:
    # Prefer system fonts; fall back to default bitmap font.
    if bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(text: str, max_chars: int) -> str:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for word in words:
        trial = (" ".join(cur + [word])).strip()
        if len(trial) <= max_chars:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines[:4])


def _draw_signal(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    req: ComposeRequest,
    colors: BrandColors,
    accent: str,
) -> None:
    # Orange pulse dot
    r = 18
    draw.ellipse((72, 72, 72 + r * 2, 72 + r * 2), fill=colors.orange)
    # Thin geometric lines
    draw.line((72, 200, w - 72, 200), fill=colors.gray, width=1)
    variant = req.layout_variant
    y = 280 if variant != "signal_03" else 220
    title = _wrap(req.marker_label, 14)
    draw.multiline_text(
        (72, y),
        title,
        font=_font(72, bold=True),
        fill=colors.black,
        spacing=12,
    )
    if req.secondary_signal:
        draw.text(
            (72, y + 280),
            req.secondary_signal.upper(),
            font=_font(28),
            fill=accent,
        )
    # Corner geometry
    draw.arc((w - 280, h - 280, w - 40, h - 40), 200, 340, fill=accent, width=2)


def _draw_typography(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    req: ComposeRequest,
    colors: BrandColors,
    accent: str,
) -> None:
    _ = accent
    parts = req.marker_label.split()
    text = (
        f"{parts[0]}\n{' '.join(parts[1:])}"
        if len(parts) >= 2
        else _wrap(req.marker_label, 10)
    )
    draw.multiline_text(
        (64, h // 3),
        text,
        font=_font(96, bold=True),
        fill=colors.black,
        spacing=8,
    )
    draw.rectangle((64, h - 120, 64 + 80, h - 112), fill=colors.orange)


def _draw_orbit(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    req: ComposeRequest,
    colors: BrandColors,
    accent: str,
) -> None:
    cx, cy = w // 2, h // 2 - 40
    for i, radius in enumerate((180, 280, 380)):
        color = colors.orange if i == 0 else (accent if i == 1 else colors.gray)
        draw.arc(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            start=40 + i * 20,
            end=300 + i * 10,
            fill=color,
            width=2,
        )
    # Sweep line
    angle = math.radians(55)
    draw.line(
        (cx, cy, cx + int(360 * math.cos(angle)), cy + int(360 * math.sin(angle))),
        fill=colors.orange,
        width=2,
    )
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=colors.orange)
    title = _wrap(req.marker_label, 12)
    bbox = draw.multiline_textbbox((0, 0), title, font=_font(48, bold=True), spacing=8)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.multiline_text(
        ((w - tw) // 2, cy - th // 2),
        title,
        font=_font(48, bold=True),
        fill=colors.black,
        spacing=8,
        align="center",
    )


def _draw_category(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    req: ComposeRequest,
    colors: BrandColors,
    accent: str,
) -> None:
    # Soft accent band
    draw.rectangle((0, 0, w, 160), fill=accent)
    cat = (req.category or "other").upper()
    draw.text((72, 56), cat, font=_font(36, bold=True), fill=RADAR_PAPER)
    draw.multiline_text(
        (72, 280),
        _wrap(req.marker_label, 14),
        font=_font(64, bold=True),
        fill=colors.black,
        spacing=10,
    )
    draw.line((72, 520, w - 72, 520), fill=colors.gray, width=1)
    if req.secondary_signal:
        draw.text((72, 560), req.secondary_signal, font=_font(28), fill=colors.gray)


def _draw_data(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    req: ComposeRequest,
    colors: BrandColors,
    accent: str,
) -> None:
    point = req.data_point or req.marker_label
    draw.ellipse((w // 2 - 220, h // 2 - 220, w // 2 + 220, h // 2 + 220), outline=accent, width=3)
    bbox = draw.textbbox((0, 0), point, font=_font(96, bold=True))
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, h // 2 - 60), point, font=_font(96, bold=True), fill=colors.black)
    draw.text(
        (72, h - 200),
        req.marker_label,
        font=_font(28),
        fill=colors.gray,
    )


def _draw_city(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    req: ComposeRequest,
    colors: BrandColors,
    accent: str,
) -> None:
    # Neutral geometry placeholder for city branding assets
    for i in range(4):
        y = 180 + i * 140
        draw.line((80, y, w - 80, y), fill=accent if i % 2 == 0 else colors.gray, width=1)
    city = (req.city_label or "ГОРОД").upper()
    draw.text((72, 72), city, font=_font(28), fill=colors.gray)
    draw.multiline_text(
        (72, 320),
        _wrap(req.marker_label, 14),
        font=_font(64, bold=True),
        fill=colors.black,
        spacing=10,
    )
    draw.rectangle((72, h - 160, 120, h - 112), fill=colors.orange)


def _draw_footer(draw: ImageDraw.ImageDraw, w: int, h: int, colors: BrandColors) -> None:
    draw.text((72, h - 72), "РАДАР", font=_font(22, bold=True), fill=colors.black)
    draw.text((w - 200, h - 72), "вакансии", font=_font(20), fill=colors.gray)

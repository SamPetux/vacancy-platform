#!/usr/bin/env python3
"""Generate a local golden-set of composed visuals + sample collection texts.

Usage (from backend/):
  python -m scripts.generate_content_golden_set

Writes PNGs under assets/generated/golden/ and a summary JSON.
Does not publish to VK.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as script from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4

from app.content.collections import CollectionDraft, render_collection_text
from app.content.creative_context import build_creative_context
from app.content.markers import MARKERS, MarkerKey, marker_label
from app.content.visual.composer import ComposeRequest, compose_card
from app.content.visual.families import ACTIVE_FAMILIES, category_accent, default_layouts_for_family
from app.content.visual.rotation import RecentVisual, select_visual
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.availability import assess_availability

OUT = Path(__file__).resolve().parents[2] / "assets" / "generated" / "golden"


def _vac(**kwargs: object) -> Vacancy:
    base = {
        "id": uuid4(),
        "city_id": uuid4(),
        "source_id": uuid4(),
        "source_item_id": "golden",
        "raw_text": "x",
        "fingerprint": str(uuid4()),
        "title": "Специалист",
        "company_name": "Компания",
        "category": "it",
        "quality_score": 65.0,
        "feed_score": 50.0,
        "flags": [],
        "duties": "Разработка продуктовых фич, код-ревью, участие в планировании спринтов и релизах.",
        "benefits": "ДМС, обучение, гибкий график и компенсация обедов.",
        "experience_required": "от 2 лет",
        "salary_from": 120000.0,
        "salary_to": 180000.0,
        "schedule": "5/2",
        "remote_type": "hybrid",
    }
    base.update(kwargs)
    return Vacancy(**base)  # type: ignore[arg-type]


def _score(v: Vacancy, **kwargs: float) -> VacancyScore:
    data = {
        "vacancy_id": v.id,
        "salary": 20.0,
        "workload": 11.0,
        "flexibility": 8.0,
        "company": 11.0,
        "experience_value": 12.0,
        "accessibility": 7.0,
        "transparency": 8.0,
        "vqs_total": float(v.quality_score or 0),
        "feed_score": float(v.feed_score or 0),
        "audience_interest": 55.0,
    }
    data.update(kwargs)
    return VacancyScore(**data)  # type: ignore[arg-type]


PROFILES: list[dict[str, object]] = [
    {"title": "Python-разработчик", "category": "it", "remote_type": "remote"},
    {"title": "Инженер-конструктор", "category": "engineering", "schedule": "5/2"},
    {"title": "Медсестра", "category": "medicine", "experience_required": "от 1 года"},
    {"title": "SMM-менеджер", "category": "marketing", "remote_type": "hybrid"},
    {"title": "Учитель математики", "category": "education"},
    {"title": "Кассир", "category": "mass", "experience_required": "без опыта", "salary_from": 45000.0, "salary_to": 55000.0},
    {"title": "Официант", "category": "hospitality", "schedule": "2/2", "experience_required": "без опыта"},
    {"title": "Финансовый аналитик", "category": "office", "salary_from": 150000.0},
    {"title": "Логист", "category": "logistics"},
    {"title": "Product Manager", "category": "it", "quality_score": 74.0, "feed_score": 60.0},
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    recent: list[RecentVisual] = []
    summary: list[dict[str, object]] = []

    # 30+ visuals across families/markers/categories
    idx = 0
    while len(summary) < 30:
        profile = PROFILES[idx % len(PROFILES)]
        v = _vac(**profile)
        s = _score(v)
        avail = assess_availability(v)
        pct = 80.0 if idx % 5 == 0 else None
        sample = 25 if pct else 0
        freq = 0.015 if idx % 7 == 0 else 0.08
        ctx = build_creative_context(
            v,
            s,
            availability=avail,
            salary_percentile=pct,
            salary_sample=sample,
            role_frequency=freq,
            recent_markers=[r.marker_key for r in recent],
            recent_families=[r.family for r in recent],
        )
        data_point = None
        if avail.schedule_label in {"2/2", "3/3", "5/2"}:
            data_point = avail.schedule_label
        elif avail.experience_label == "без опыта":
            data_point = "0 ЛЕТ ОПЫТА"
        choice = select_visual(
            marker_key=ctx.creative_type,
            category=ctx.category,
            preferred_family=ctx.visual_family,
            recent=recent,
            data_point_available=data_point is not None,
        )
        path = OUT / f"{len(summary):02d}_{choice.family.value}_{ctx.creative_type}.png"
        compose_card(
            ComposeRequest(
                marker_label=marker_label(ctx.creative_type),
                visual_family=choice.family.value,
                layout_variant=choice.layout_variant,
                category=ctx.category,
                secondary_signal=ctx.secondary_signal,
                data_point=data_point,
                city_label="Нижний Новгород",
                accent=choice.accent,
            ),
            output_path=path,
        )
        recent.append(
            RecentVisual(
                family=choice.family.value,
                layout_variant=choice.layout_variant,
                marker_key=ctx.creative_type,
                category=ctx.category,
                accent=choice.accent,
            )
        )
        if len(recent) > 8:
            recent = recent[-8:]
        summary.append(
            {
                "file": path.name,
                "marker": ctx.creative_type,
                "label": marker_label(ctx.creative_type),
                "family": choice.family.value,
                "layout": choice.layout_variant,
                "category": ctx.category,
                "title": v.title,
            }
        )
        idx += 1

    # Sample collections (text only)
    collections = []
    for theme, title in (
        ("weekly_highlights", "5 интересных вакансий недели в Нижнем"),
        ("no_experience", "5 вакансий без опыта"),
        ("category", "5 предложений для инженеров"),
        ("salary_floor", "Где в Нижнем предлагают от 100 тысяч?"),
        ("rare_roles", "Необычная работа в Нижнем"),
        ("career_path", "5 вакансий для карьерного шага"),
        ("flex_format", "Работа с гибким графиком"),
    ):
        draft = CollectionDraft(
            theme=theme,
            title=title,
            intro="Подборка из тестовых данных golden-set.",
            vacancy_ids=[uuid4() for _ in range(3)],
            items=[
                {
                    "index": i,
                    "title": f"Роль {i}",
                    "salary": "от 80 тыс. ₽",
                    "company": f"Компания {i}",
                    "source_url": f"https://example.com/{i}",
                }
                for i in range(1, 4)
            ],
            disclaimer=(
                "По нашей выборке за 30 дн., N=40. Это не статистика всего рынка."
                if theme == "salary_floor"
                else None
            ),
            fingerprint=theme,
            sample_size=40,
            period_days=30 if theme == "salary_floor" else 7,
        )
        text_path = OUT / f"collection_{theme}.txt"
        text_path.write_text(render_collection_text(draft), encoding="utf-8")
        collections.append({"theme": theme, "file": text_path.name})

    meta = {
        "visuals": summary,
        "collections": collections,
        "families": [f.value for f in ACTIVE_FAMILIES],
        "markers": [m.value for m in MarkerKey],
        "note": "Collections text-only; mass publish remains gated.",
    }
    (OUT / "summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(summary)} visuals + {len(collections)} collections to {OUT}")


if __name__ == "__main__":
    main()

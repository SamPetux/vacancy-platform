"""Content Engine unit tests — AIS, markers, creative context, visual, collections."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.content.audience_interest import compute_audience_interest
from app.content.collections import CollectionDraft, render_collection_text
from app.content.creative_context import build_creative_context
from app.content.markers import MARKERS, MarkerKey, marker_label
from app.content.visual.composer import ComposeRequest, compose_card
from app.content.visual.families import VisualFamily, category_accent
from app.content.visual.rotation import RecentVisual, select_visual
from app.db.base import Base
from app.models import ContentAnalyticsSnapshot, ContentItem
from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.publishing.availability import assess_availability
from app.publishing.editorial import assign_grade, build_editorial
from app.publishing.models import EditorialRating, PostDraft, TemplateMode
from app.publishing.render import render_post


def _vacancy(**kwargs: object) -> Vacancy:
    defaults = {
        "id": uuid4(),
        "city_id": uuid4(),
        "source_id": uuid4(),
        "source_item_id": "x",
        "raw_text": "test",
        "fingerprint": "fp",
        "title": "Инженер-конструктор",
        "company_name": "Завод",
        "category": "engineering",
        "quality_score": 72.0,
        "feed_score": 58.0,
        "salary_from": 110000.0,
        "salary_to": 160000.0,
        "duties": (
            "Разработка КД, согласование с производством, "
            "сопровождение изделий на всех этапах."
        ),
        "benefits": (
            "ДМС, компенсация питания, обучение за счёт компании "
            "и стабильный график."
        ),
        "experience_required": "от 2 лет",
        "remote_type": "office",
        "schedule": "5/2",
        "flags": [],
    }
    defaults.update(kwargs)
    return Vacancy(**defaults)  # type: ignore[arg-type]


def _score(vacancy: Vacancy) -> VacancyScore:
    return VacancyScore(
        vacancy_id=vacancy.id,
        salary=22,
        workload=12,
        flexibility=7,
        company=12,
        experience_value=13,
        accessibility=7,
        transparency=8,
        vqs_total=72,
        feed_score=58,
        audience_interest=0,
    )


def test_content_tables_registered() -> None:
    assert "content_items" in Base.metadata.tables
    assert "content_analytics_snapshots" in Base.metadata.tables
    assert ContentItem.__tablename__ == "content_items"
    assert ContentAnalyticsSnapshot.__tablename__ == "content_analytics_snapshots"


def test_audience_interest_deterministic() -> None:
    v = _vacancy()
    s = _score(v)
    a = compute_audience_interest(v, s, role_frequency=0.01, salary_percentile=80)
    b = compute_audience_interest(v, s, role_frequency=0.01, salary_percentile=80)
    assert a.total == b.total
    assert 0 <= a.total <= 100
    assert "novelty_role" in a.explanation["components"]


def test_above_market_requires_cohort() -> None:
    v = _vacancy()
    s = _score(v)
    avail = assess_availability(v)
    # High salary component alone must NOT yield ABOVE_MARKET
    ctx_no_cohort = build_creative_context(
        v,
        s,
        availability=avail,
        salary_percentile=None,
        salary_sample=0,
    )
    assert ctx_no_cohort.creative_type != MarkerKey.ABOVE_MARKET.value

    ctx_with = build_creative_context(
        v,
        s,
        availability=avail,
        salary_percentile=80,
        salary_sample=20,
    )
    assert ctx_with.creative_type == MarkerKey.ABOVE_MARKET.value


def test_good_start_requires_no_experience() -> None:
    v = _vacancy(
        experience_required="без опыта",
        quality_score=60,
        feed_score=48,
    )
    s = _score(v)
    s.experience_value = 8
    s.accessibility = 8
    s.company = 10
    ctx = build_creative_context(v, s, availability=assess_availability(v))
    assert ctx.creative_type in {
        MarkerKey.GOOD_START.value,
        MarkerKey.NO_EXPERIENCE.value,
        MarkerKey.STRONG_OFFER.value,
        MarkerKey.WORTH_NOTICING.value,
        MarkerKey.DATA_POINT.value,
    }


def test_public_render_hides_grade() -> None:
    draft = PostDraft(
        title="Аналитик",
        company="Компания",
        salary="от 100 тыс. ₽",
        intro="Короткое описание.",
        meta=["Нижний Новгород"],
        blocks=[],
        editorial=EditorialRating(
            grade="A+",
            label="КАРЬЕРНЫЙ ШАГ",
            reason="Интересные задачи и полезный опыт.",
            show_grade_publicly=False,
        ),
        source_url="https://example.com",
        mode=TemplateMode.STANDARD,
        variant=0,
    )
    text = render_post(draft)
    assert "▷ КАРЬЕРНЫЙ ШАГ" in text
    assert "A+" not in text.split("▷")[1].split("\n")[0]


def test_build_editorial_uses_marker_label() -> None:
    v = _vacancy()
    s = _score(v)
    editorial = build_editorial(v, assess_availability(v), s)
    assert editorial is not None
    assert editorial.show_grade_publicly is False
    assert editorial.label == editorial.label.upper() or editorial.label in {
        m.label for m in MARKERS.values()
    }
    assert assign_grade(vqs=72, feed_score=58) == "A+"
    assert editorial.grade == "A+"


def test_visual_rotation_avoids_repeat() -> None:
    recent = [
        RecentVisual("RADAR_SIGNAL", "signal_01", "STRONG_OFFER", "it", "#5B7C99"),
        RecentVisual("RADAR_SIGNAL", "signal_02", "CAREER_STEP", "engineering", "#6E7378"),
        RecentVisual("RADAR_SIGNAL", "signal_03", "FLEX_FORMAT", "it", "#5B7C99"),
    ]
    choice = select_visual(
        marker_key="FLEX_FORMAT",
        category="it",
        recent=recent,
        data_point_available=False,
    )
    # After three SIGNAL posts, rotation should prefer another family.
    assert choice.family != VisualFamily.RADAR_SIGNAL


def test_compose_card_writes_png(tmp_path: Path) -> None:
    out = tmp_path / "card.png"
    img = compose_card(
        ComposeRequest(
            marker_label="ХОРОШИЙ СТАРТ",
            visual_family="RADAR_SIGNAL",
            layout_variant="signal_02",
            category="engineering",
            secondary_signal="Без опыта",
            city_label="Нижний Новгород",
            accent=category_accent("engineering"),
        ),
        output_path=out,
    )
    assert out.is_file()
    assert img.size == (1080, 1080)


def test_compose_all_families(tmp_path: Path) -> None:
    for fam in (
        "RADAR_SIGNAL",
        "RADAR_TYPOGRAPHY",
        "RADAR_ORBIT",
        "RADAR_CATEGORY",
        "RADAR_DATA",
        "RADAR_CITY",
    ):
        out = tmp_path / f"{fam}.png"
        compose_card(
            ComposeRequest(
                marker_label="РЕДКАЯ РОЛЬ",
                visual_family=fam,
                layout_variant="signal_01",
                category="it",
                data_point="2/2",
                city_label="Город",
            ),
            output_path=out,
        )
        assert out.is_file()


def test_collection_text_render() -> None:
    draft = CollectionDraft(
        theme="weekly_highlights",
        title="5 интересных вакансий недели",
        intro="На этой неделе нашли несколько предложений.",
        vacancy_ids=[uuid4(), uuid4()],
        items=[
            {
                "index": 1,
                "title": "Инженер",
                "salary": "от 110 тыс. ₽",
                "company": "Компания X",
                "source_url": "https://a.example",
            },
            {
                "index": 2,
                "title": "Аналитик",
                "salary": "120–160 тыс. ₽",
                "company": "Компания Y",
                "source_url": "https://b.example",
            },
        ],
        disclaimer=None,
        fingerprint="abc",
        sample_size=40,
        period_days=7,
    )
    text = render_collection_text(draft)
    assert "01 / Инженер" in text
    assert "https://a.example" in text
    assert "Открыть вакансии" in text


def test_marker_labels() -> None:
    assert marker_label(MarkerKey.CAREER_STEP) == "КАРЬЕРНЫЙ ШАГ"
    assert "НОВАЯ ВАКАНСИЯ" not in {m.label for m in MARKERS.values()}


def test_vacancy_score_has_ais_field() -> None:
    assert "audience_interest" in VacancyScore.__table__.c
    assert "audience_interest_score" in Vacancy.__table__.c

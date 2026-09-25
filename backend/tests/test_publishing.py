"""Tests for section split and VK publication Template Engine."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.parsing.extract import parse_vacancy_text
from app.parsing.sections import is_stub_requirements, split_description_sections
from app.publishing.editorial import assign_grade
from app.publishing.engine import TemplateEngine
from app.publishing.salary import format_salary_line


def test_split_superjob_candidat_sections() -> None:
    blob = """
Обязанности:
• УЗИ диагностика
• Ведение документации

Требования:
• Опыт работы по специальности от 3 лет
• Сертификат УЗИ

Мы предлагаем:
• Доход от 100000 рублей
• ДМС после испытательного срока
"""
    split = split_description_sections(blob)
    assert split.duties is not None and "УЗИ" in split.duties
    assert split.requirements is not None and "3 лет" in split.requirements
    assert split.benefits is not None and "ДМС" in split.benefits


def test_parse_structured_superjob_splits_candidat() -> None:
    parsed = parse_vacancy_text(
        "Врач-УЗИ",
        structured={
            "name": "Врач-УЗИ",
            "employer": {"name": "Медцентр"},
            "salary": {"from": 100000, "currency": "RUB"},
            "experience": {"name": "От 3 лет"},
            "schedule": {"name": "Полный рабочий день"},
            "snippet": {
                "requirement": (
                    "Обязанности:\n• УЗИ диагностика\n"
                    "Требования:\n• Опыт от 3 лет\n"
                    "Мы предлагаем:\n• ДМС\n• от 100000 рублей"
                ),
                "responsibility": None,
            },
        },
    )
    assert parsed.duties is not None and "УЗИ" in parsed.duties
    assert parsed.requirements is not None and "Опыт" in parsed.requirements
    assert parsed.benefits is not None and "ДМС" in parsed.benefits


def test_stub_requirements_detected() -> None:
    assert is_stub_requirements("опыт: без опыта; образование: Не указано")
    assert not is_stub_requirements(
        "Опыт работы с Python от двух лет, умение самостоятельно вести задачи"
    )


def test_salary_format() -> None:
    assert format_salary_line(120000, 160000) == "120–160 тыс. ₽"
    assert format_salary_line(95000, None) == "от 95 тыс. ₽"
    assert format_salary_line(None, 180000) == "до 180 тыс. ₽"
    assert format_salary_line(None, None) is None


def test_grade_thresholds() -> None:
    assert assign_grade(vqs=74, feed_score=56) == "A+"
    assert assign_grade(vqs=66, feed_score=49) == "A"
    assert assign_grade(vqs=60, feed_score=45) == "B+"
    assert assign_grade(vqs=50, feed_score=40) == "B"


def test_template_engine_renders_standard_post() -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        title="Программист 1С",
        company_name='АО "ЦКБ ЛАЗУРИТ"',
        salary_from=143500,
        salary_to=153850,
        salary_currency="RUB",
        schedule="Полный рабочий день",
        remote_type=None,
        experience_required="от 1 года",
        duties=(
            "Внедрение и доработка конфигураций на платформе 1С 8.3. "
            "Разработка внешних отчётов и обработок. "
            "Оптимизация существующих решений."
        ),
        requirements="опыт: от 1 года; образование: Высшее",
        benefits=None,
        address="г Нижний Новгород",
        district=None,
        category="it",
        employment_type=None,
        quality_score=71.3,
        feed_score=48.0,
        source_url="https://example.com/vacancy/1",
        clean_text=None,
        raw_text="Программист 1С Python PostgreSQL Docker",
    )
    engine = TemplateEngine()
    draft, text = engine.generate(vacancy)  # type: ignore[arg-type]
    assert "Программист 1С — АО" in text
    assert "144–154 тыс. ₽" in text
    assert "► Задачи:" in text
    assert "▷" in text
    assert "Открыть вакансию —" in text
    assert "https://example.com/vacancy/1" in text
    assert draft.mode.value in {"compact", "standard", "extended"}
    assert "🔥" not in text
    assert len(text) <= 1500


def test_template_engine_omits_missing_salary() -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        title="Маркетолог",
        company_name="Тест",
        salary_from=None,
        salary_to=None,
        salary_currency="RUB",
        schedule="удалённо",
        remote_type="remote",
        experience_required="От 3 лет",
        duties=None,
        requirements="Опыт в продуктовой аналитике от трёх лет, SQL и умение читать метрики.",
        benefits=None,
        address=None,
        district=None,
        category="marketing",
        employment_type=None,
        quality_score=54.0,
        feed_score=50.0,
        source_url=None,
        clean_text=None,
        raw_text="Маркетолог SQL",
    )
    _, text = TemplateEngine().generate(vacancy)  # type: ignore[arg-type]
    assert "тыс. ₽" not in text
    assert "зарплата не указана" not in text.lower()
    assert "удалённо" in text

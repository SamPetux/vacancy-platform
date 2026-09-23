"""Unit tests for parsing and scoring."""

from app.deduplication.service import build_fingerprint, is_near_duplicate
from app.parsing.extract import parse_vacancy_text
from app.parsing.vacancy_detect import is_vacancy_text
from app.scoring.feed_score import compute_feed_score
from app.scoring.vqs import compute_vqs


def test_detect_vacancy() -> None:
    text = "Вакансия: менеджер по продажам. Зарплата 80 000 руб. График 5/2."
    assert is_vacancy_text(text) is True
    assert is_vacancy_text("Ищу работу менеджером, рассмотрю предложения") is False


def test_parse_and_score() -> None:
    text = (
        "Вакансия: Аналитик данных\n"
        "Компания ООО Ромашка\n"
        "Зарплата 120 000–150 000 ₽\n"
        "График 5/2, 8 часов\n"
        "Опыт от 2 лет\n"
        "Требования: SQL, Python\n"
        "Тел. +7 999 123-45-67"
    )
    parsed = parse_vacancy_text(text)
    assert parsed.salary_from == 120000
    assert parsed.schedule == "5/2"
    vqs = compute_vqs(parsed, text)
    assert 40 <= vqs.total <= 100
    feed = compute_feed_score(
        vqs=vqs.total,
        parsed=parsed,
        flags=vqs.flags,
        source_created_at=None,
        category_counts_today={},
        company_counts_today={},
    )
    assert feed.score > 0


def test_near_duplicate() -> None:
    a = "Водитель категории B. Компания X. 90000 руб. +79991234567"
    b = "Компания X ищет водителя з/п до 90 тысяч тел. +7 999 123-45-67"
    assert is_near_duplicate("Водитель", "Компания X", a, "Водитель", "Компания X", b)
    fp = build_fingerprint(
        title="Водитель",
        company="X",
        salary_from=90000,
        salary_to=None,
        contact="+79991234567",
        text=a,
    )
    assert len(fp.fingerprint) == 64

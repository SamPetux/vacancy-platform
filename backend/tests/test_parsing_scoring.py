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


def test_location_filter_rejects_foreign_settlement() -> None:
    from app.parsing.location import build_location_policy, evaluate_work_location

    policy = build_location_policy(
        city_name="Нижний Новгород",
        aliases=["нижний новгород", "г нижний новгород"],
        allow_remote=True,
    )
    text = (
        "Педагог дополнительного образования\n"
        "Ищем кандидата из: г. Нижний Новгород и др. городов\n"
        "посёлок Тазовский\n"
        "Место работы: Не имеет значения\n"
    )
    verdict = evaluate_work_location(text=text, policy=policy)
    assert verdict.allowed is False
    assert verdict.flag == "OUT_OF_CITY"
    assert verdict.work_location is not None
    assert "тазов" in (verdict.work_location or "").lower()


def test_location_filter_allows_local_address() -> None:
    from app.parsing.location import build_location_policy, evaluate_work_location

    policy = build_location_policy(
        city_name="Нижний Новгород",
        aliases=["нижний новгород"],
    )
    text = (
        "Шлифовщик\n"
        "Адрес: Нижегородская область, г Нижний Новгород, Жиркомбината шоссе, 22а\n"
    )
    verdict = evaluate_work_location(text=text, policy=policy, address=None)
    assert verdict.allowed is True
    assert verdict.reason == "local_work_location"


def test_location_filter_rejects_oblast_town() -> None:
    from app.parsing.location import build_location_policy, evaluate_work_location

    policy = build_location_policy(
        city_name="Нижний Новгород",
        aliases=["нижний новгород"],
    )
    text = "Адрес: Нижегородская область, г Дзержинск, Чапаева улица, 28"
    verdict = evaluate_work_location(text=text, policy=policy)
    assert verdict.allowed is False


def test_location_filter_rejects_superjob_address_field() -> None:
    from app.parsing.location import build_location_policy, evaluate_work_location

    policy = build_location_policy(
        city_name="Нижний Новгород",
        aliases=["нижний новгород"],
    )
    text = (
        "Педагог дополнительного образования\n"
        "Место работы: Не имеет значения\n"
        "Адрес: посёлок Тазовский\n"
    )
    verdict = evaluate_work_location(
        text=text,
        policy=policy,
        structured={"address": "посёлок Тазовский"},
    )
    assert verdict.allowed is False
    assert "тазов" in (verdict.work_location or "").lower()


def test_location_filter_rejects_country_in_title() -> None:
    from app.parsing.location import build_location_policy, evaluate_work_location

    policy = build_location_policy(
        city_name="Нижний Новгород",
        aliases=["нижний новгород"],
    )
    text = "Инженер-дефектоскопист (Египет)\nМесто работы: Не имеет значения\n"
    verdict = evaluate_work_location(text=text, policy=policy)
    assert verdict.allowed is False


def test_location_filter_rejects_home_care_false_remote() -> None:
    from app.parsing.location import build_location_policy, evaluate_work_location

    policy = build_location_policy(
        city_name="Нижний Новгород",
        aliases=["нижний новгород"],
        allow_remote=True,
    )
    text = (
        "врач-терапевт участковый\n"
        "Оказывать помощь в стационаре на дому.\n"
        "Адрес: Нижегородская область, г Арзамас, Зелёная улица, 2\n"
    )
    verdict = evaluate_work_location(
        text=text,
        policy=policy,
        address="Нижегородская область, г Арзамас, Зелёная улица, 2",
        remote_type="remote",  # sticky false positive
    )
    assert verdict.allowed is False
    assert verdict.reason == "non_local_work_location"

"""Stage 2 domain model smoke tests."""

from app.db.base import Base
from app.models import (
    City,
    CollectionRun,
    Company,
    RawItem,
    ScoringConfig,
    Source,
    Vacancy,
    VacancyScore,
)
from app.models.enums import (
    CollectionRunStatus,
    RawItemStatus,
    SourceHealthStatus,
    SourceType,
    VacancyStatus,
)
from app.models.scoring_config import DEFAULT_VQS_WEIGHTS


def test_all_domain_tables_registered() -> None:
    expected = {
        "cities",
        "sources",
        "raw_items",
        "companies",
        "vacancies",
        "vacancy_scores",
        "collection_runs",
        "scoring_configs",
    }
    assert expected.issubset(set(Base.metadata.tables))


def test_enum_values() -> None:
    assert SourceType.VK == "vk"
    assert SourceHealthStatus.RATE_LIMITED == "rate_limited"
    assert VacancyStatus.WAITING_MODERATION == "waiting_moderation"
    assert RawItemStatus.SKIPPED_NOT_VACANCY == "skipped_not_vacancy"
    assert CollectionRunStatus.FAILED == "failed"


def test_company_metadata_column_name() -> None:
    col = Company.__table__.c.metadata
    assert col.name == "metadata"
    assert Company.extra_metadata.property.columns[0] is col


def test_key_indexes_present() -> None:
    vacancy_indexes = {idx.name for idx in Vacancy.__table__.indexes}
    assert "ix_vacancies_fingerprint" in vacancy_indexes
    assert "ix_vacancies_moderation_status" in vacancy_indexes
    assert "ix_vacancies_feed_score" in vacancy_indexes

    raw_indexes = {idx.name for idx in RawItem.__table__.indexes}
    assert "ix_raw_items_content_hash" in raw_indexes

    city_indexes = {idx.name for idx in City.__table__.indexes}
    assert "ix_cities_slug" in city_indexes or any(
        list(idx.columns.keys()) == ["slug"] for idx in City.__table__.indexes
    )


def test_unique_constraints() -> None:
    source_uq = {c.name for c in Source.__table__.constraints if c.name}
    assert "uq_sources_city_type_external" in source_uq

    raw_uq = {c.name for c in RawItem.__table__.constraints if c.name}
    assert "uq_raw_items_source_item" in raw_uq

    assert Vacancy.__table__.c.raw_item_id.unique is True
    assert VacancyScore.__table__.c.vacancy_id.unique is True


def test_default_vqs_weights_sum_to_100() -> None:
    assert sum(DEFAULT_VQS_WEIGHTS.values()) == 100


def test_collection_run_and_scoring_config_importable() -> None:
    assert CollectionRun.__tablename__ == "collection_runs"
    assert ScoringConfig.__tablename__ == "scoring_configs"

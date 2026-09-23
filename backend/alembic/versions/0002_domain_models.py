"""Stage 2 domain models.

Revision ID: 0002_domain_models
Revises: 0001_foundation
Create Date: 2026-03-22

Creates City, Source, RawItem, Company, Vacancy, VacancyScore,
CollectionRun, and ScoringConfig tables with indexes and constraints.
Enums are stored as VARCHAR for simpler future migrations.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_domain_models"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("region", sa.String(length=255), nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="Europe/Moscow",
            nullable=False,
        ),
        sa.Column("hh_area_id", sa.Integer(), nullable=True),
        sa.Column("min_vqs", sa.Float(), server_default="55", nullable=False),
        sa.Column("min_feed_score", sa.Float(), server_default="60", nullable=False),
        sa.Column("target_items_per_day", sa.Integer(), server_default="20", nullable=False),
        sa.Column("max_per_company_per_day", sa.Integer(), server_default="2", nullable=False),
        sa.Column("max_per_category_per_day", sa.Integer(), server_default="3", nullable=False),
        sa.Column("hh_fallback_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("hh_fallback_threshold", sa.Integer(), server_default="8", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cities_slug", "cities", ["slug"], unique=True)

    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="2", nullable=False),
        sa.Column("poll_interval_minutes", sa.Integer(), server_default="1440", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("last_item_id", sa.String(length=255), nullable=True),
        sa.Column("last_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "health_status",
            sa.String(length=32),
            server_default="online",
            nullable=False,
        ),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority >= 1 AND priority <= 3",
            name="ck_sources_priority_range",
        ),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "city_id",
            "source_type",
            "external_id",
            name="uq_sources_city_type_external",
        ),
    )
    op.create_index("ix_sources_city_id", "sources", ["city_id"], unique=False)
    op.create_index("ix_sources_last_item_id", "sources", ["last_item_id"], unique=False)
    op.create_index("ix_sources_last_timestamp", "sources", ["last_timestamp"], unique=False)
    op.create_index("ix_sources_last_polled_at", "sources", ["last_polled_at"], unique=False)

    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("normalized_name", sa.String(length=512), nullable=False),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_city_id", "companies", ["city_id"], unique=False)
    op.create_index(
        "ix_companies_normalized_name",
        "companies",
        ["normalized_name"],
        unique=False,
    )

    op.create_table(
        "raw_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("source_item_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="new", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "source_item_id", name="uq_raw_items_source_item"),
    )
    op.create_index("ix_raw_items_source_id", "raw_items", ["source_id"], unique=False)
    op.create_index("ix_raw_items_city_id", "raw_items", ["city_id"], unique=False)
    op.create_index("ix_raw_items_status", "raw_items", ["status"], unique=False)
    op.create_index("ix_raw_items_content_hash", "raw_items", ["content_hash"], unique=False)

    op.create_table(
        "scoring_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=True),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "feed_weights",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "thresholds",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "suspicious_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "category_coefficients",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scoring_configs_city_id", "scoring_configs", ["city_id"], unique=False)
    op.create_index("ix_scoring_configs_is_active", "scoring_configs", ["is_active"], unique=False)

    op.create_table(
        "collection_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), server_default="running", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collection_runs_city_id", "collection_runs", ["city_id"], unique=False)
    op.create_index("ix_collection_runs_status", "collection_runs", ["status"], unique=False)

    op.create_table(
        "vacancies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("raw_item_id", sa.Uuid(), nullable=True),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("source_item_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("company_name", sa.String(length=512), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("professional_role", sa.String(length=255), nullable=True),
        sa.Column("salary_from", sa.Float(), nullable=True),
        sa.Column("salary_to", sa.Float(), nullable=True),
        sa.Column("salary_currency", sa.String(length=8), nullable=True),
        sa.Column("salary_period", sa.String(length=32), nullable=True),
        sa.Column("salary_net_estimate", sa.Float(), nullable=True),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("schedule", sa.String(length=128), nullable=True),
        sa.Column("shifts", sa.String(length=128), nullable=True),
        sa.Column("hours_per_day", sa.Float(), nullable=True),
        sa.Column("days_per_week", sa.Float(), nullable=True),
        sa.Column("remote_type", sa.String(length=64), nullable=True),
        sa.Column("experience_required", sa.String(length=128), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("duties", sa.Text(), nullable=True),
        sa.Column("benefits", sa.Text(), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("district", sa.String(length=255), nullable=True),
        sa.Column("contact_type", sa.String(length=64), nullable=True),
        sa.Column("contact", sa.String(length=512), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("feed_score", sa.Float(), nullable=True),
        sa.Column(
            "flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("score_explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "moderation_status",
            sa.String(length=64),
            server_default="new",
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("duplicate_of_id", sa.Uuid(), nullable=True),
        sa.Column("ranked_position", sa.Integer(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["vacancies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["raw_item_id"], ["raw_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_item_id"),
    )
    op.create_index("ix_vacancies_city_id", "vacancies", ["city_id"], unique=False)
    op.create_index("ix_vacancies_source_id", "vacancies", ["source_id"], unique=False)
    op.create_index("ix_vacancies_company_id", "vacancies", ["company_id"], unique=False)
    op.create_index("ix_vacancies_category", "vacancies", ["category"], unique=False)
    op.create_index("ix_vacancies_feed_score", "vacancies", ["feed_score"], unique=False)
    op.create_index(
        "ix_vacancies_moderation_status",
        "vacancies",
        ["moderation_status"],
        unique=False,
    )
    op.create_index("ix_vacancies_fingerprint", "vacancies", ["fingerprint"], unique=False)
    op.create_index("ix_vacancies_duplicate_of_id", "vacancies", ["duplicate_of_id"], unique=False)

    op.create_table(
        "vacancy_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("salary", sa.Float(), server_default="0", nullable=False),
        sa.Column("workload", sa.Float(), server_default="0", nullable=False),
        sa.Column("flexibility", sa.Float(), server_default="0", nullable=False),
        sa.Column("company", sa.Float(), server_default="0", nullable=False),
        sa.Column("experience_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("accessibility", sa.Float(), server_default="0", nullable=False),
        sa.Column("transparency", sa.Float(), server_default="0", nullable=False),
        sa.Column("vqs_total", sa.Float(), server_default="0", nullable=False),
        sa.Column("feed_score", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "components_detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vacancy_id"),
    )


def downgrade() -> None:
    op.drop_table("vacancy_scores")
    op.drop_index("ix_vacancies_duplicate_of_id", table_name="vacancies")
    op.drop_index("ix_vacancies_fingerprint", table_name="vacancies")
    op.drop_index("ix_vacancies_moderation_status", table_name="vacancies")
    op.drop_index("ix_vacancies_feed_score", table_name="vacancies")
    op.drop_index("ix_vacancies_category", table_name="vacancies")
    op.drop_index("ix_vacancies_company_id", table_name="vacancies")
    op.drop_index("ix_vacancies_source_id", table_name="vacancies")
    op.drop_index("ix_vacancies_city_id", table_name="vacancies")
    op.drop_table("vacancies")
    op.drop_index("ix_collection_runs_status", table_name="collection_runs")
    op.drop_index("ix_collection_runs_city_id", table_name="collection_runs")
    op.drop_table("collection_runs")
    op.drop_index("ix_scoring_configs_is_active", table_name="scoring_configs")
    op.drop_index("ix_scoring_configs_city_id", table_name="scoring_configs")
    op.drop_table("scoring_configs")
    op.drop_index("ix_raw_items_content_hash", table_name="raw_items")
    op.drop_index("ix_raw_items_status", table_name="raw_items")
    op.drop_index("ix_raw_items_city_id", table_name="raw_items")
    op.drop_index("ix_raw_items_source_id", table_name="raw_items")
    op.drop_table("raw_items")
    op.drop_index("ix_companies_normalized_name", table_name="companies")
    op.drop_index("ix_companies_city_id", table_name="companies")
    op.drop_table("companies")
    op.drop_index("ix_sources_last_polled_at", table_name="sources")
    op.drop_index("ix_sources_last_timestamp", table_name="sources")
    op.drop_index("ix_sources_last_item_id", table_name="sources")
    op.drop_index("ix_sources_city_id", table_name="sources")
    op.drop_table("sources")
    op.drop_table("cities")

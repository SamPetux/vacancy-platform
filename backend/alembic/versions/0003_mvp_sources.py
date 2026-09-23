"""Alembic revision: rename HH fallback fields to generic supplement config."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_mvp_sources"
down_revision: str | None = "0002_domain_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "cities",
        "hh_fallback_enabled",
        new_column_name="supplement_enabled",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default="true",
    )
    op.alter_column(
        "cities",
        "hh_fallback_threshold",
        new_column_name="supplement_threshold",
        existing_type=sa.Integer(),
        existing_nullable=False,
        existing_server_default="8",
    )


def downgrade() -> None:
    op.alter_column(
        "cities",
        "supplement_enabled",
        new_column_name="hh_fallback_enabled",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default="true",
    )
    op.alter_column(
        "cities",
        "supplement_threshold",
        new_column_name="hh_fallback_threshold",
        existing_type=sa.Integer(),
        existing_nullable=False,
        existing_server_default="8",
    )

"""Alembic revision: store TrudVsem region code on City."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_trudvsem_region"
down_revision: str | None = "0004_vacancy_media"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cities",
        sa.Column("trudvsem_region_code", sa.String(length=32), nullable=True),
    )
    # Nizhny Novgorod oblast OKATO region code used by opendata.trudvsem.ru
    op.execute(
        sa.text(
            "UPDATE cities SET trudvsem_region_code = '52' "
            "WHERE slug = 'nizhny-novgorod' AND trudvsem_region_code IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("cities", "trudvsem_region_code")

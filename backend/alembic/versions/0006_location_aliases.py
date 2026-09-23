"""Alembic revision: city work-location aliases for geo filter."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_location_aliases"
down_revision: str | None = "0005_trudvsem_region"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cities",
        sa.Column(
            "location_aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "cities",
        sa.Column(
            "allow_remote",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE cities
            SET location_aliases = CAST(
              '["нижний новгород", "г нижний новгород", "г. нижний новгород",
                "н. новгород", "н новгород"]' AS jsonb
            )
            WHERE slug = 'nizhny-novgorod'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("cities", "allow_remote")
    op.drop_column("cities", "location_aliases")

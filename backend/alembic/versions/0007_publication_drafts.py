"""Alembic revision: publication drafts for VK post preview."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_publication_drafts"
down_revision: str | None = "0006_location_aliases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "publication_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column(
            "structured",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("rendered_text", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="standard"),
        sa.Column("variant", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("manually_edited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vacancy_id", name="uq_publication_drafts_vacancy"),
    )
    op.create_index(
        op.f("ix_publication_drafts_vacancy_id"),
        "publication_drafts",
        ["vacancy_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_publication_drafts_vacancy_id"), table_name="publication_drafts")
    op.drop_table("publication_drafts")

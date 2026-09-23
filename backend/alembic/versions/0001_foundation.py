"""Initial schema placeholder.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-03-22

Stage 1 has no domain tables yet. Enables pg_trgm for later deduplication.
Domain entities (City, Source, RawItem, Vacancy, ...) arrive in Stage 2.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")

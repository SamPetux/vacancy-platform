"""Content Engine: AIS columns, content_items, analytics snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_content_engine"
down_revision: str | None = "0008_manual_publications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vacancy_scores",
        sa.Column(
            "audience_interest",
            sa.Float(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "vacancies",
        sa.Column("audience_interest_score", sa.Float(), nullable=True),
    )

    op.create_table(
        "content_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=64),
            server_default="VACANCY",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("vacancy_id", sa.Uuid(), nullable=True),
        sa.Column("publication_draft_id", sa.Uuid(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "creative_context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "visual",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("rendered_text", sa.Text(), server_default="", nullable=False),
        sa.Column("image_path", sa.String(length=1024), nullable=True),
        sa.Column("vk_attachment", sa.String(length=128), nullable=True),
        sa.Column("audience_interest_score", sa.Float(), nullable=True),
        sa.Column("internal_grade", sa.String(length=8), nullable=True),
        sa.Column("ranked_position", sa.Integer(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "manually_edited",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("vk_post_id", sa.Integer(), nullable=True),
        sa.Column("vk_owner_id", sa.Integer(), nullable=True),
        sa.Column("vk_url", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["publication_draft_id"],
            ["publication_drafts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_items_city_id", "content_items", ["city_id"])
    op.create_index("ix_content_items_content_type", "content_items", ["content_type"])
    op.create_index("ix_content_items_status", "content_items", ["status"])
    op.create_index("ix_content_items_vacancy_id", "content_items", ["vacancy_id"])

    op.create_table(
        "content_analytics_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.Column("vk_post_id", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Integer(), nullable=True),
        sa.Column("reposts", sa.Integer(), nullable=True),
        sa.Column("hides", sa.Integer(), nullable=True),
        sa.Column("link_clicks", sa.Integer(), nullable=True),
        sa.Column("favorites", sa.Integer(), nullable=True),
        sa.Column("subscriber_gain", sa.Integer(), nullable=True),
        sa.Column(
            "raw",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"],
            ["content_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_analytics_snapshots_content_item_id",
        "content_analytics_snapshots",
        ["content_item_id"],
    )


def downgrade() -> None:
    op.drop_table("content_analytics_snapshots")
    op.drop_table("content_items")
    op.drop_column("vacancies", "audience_interest_score")
    op.drop_column("vacancy_scores", "audience_interest")

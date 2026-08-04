"""market listing details for persona-specific scorecards

Revision ID: 0009_market_listing_details
Revises: 0008_market_pipeline
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_market_listing_details"
down_revision = "0008_market_pipeline"
branch_labels = None
depends_on = None


DETAIL_COLUMNS: tuple[sa.Column, ...] = (
    sa.Column("external_id", sa.String(length=80), nullable=True),
    sa.Column("title", sa.String(length=240), nullable=True),
    sa.Column("area", sa.String(length=80), nullable=True),
    sa.Column("address", sa.String(length=300), nullable=True),
    sa.Column("bedrooms", sa.Integer(), nullable=True),
    sa.Column("property_type", sa.String(length=80), nullable=True),
    sa.Column("source_url", sa.Text(), nullable=True),
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("market_samples")}
    for column in DETAIL_COLUMNS:
        if column.name not in existing:
            op.add_column("market_samples", column)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_market_samples_external_id "
        "ON market_samples (external_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_market_samples_area ON market_samples (area)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_market_samples_area")
    op.execute("DROP INDEX IF EXISTS ix_market_samples_external_id")
    existing = {c["name"] for c in sa.inspect(bind).get_columns("market_samples")}
    for name in reversed([str(column.name) for column in DETAIL_COLUMNS]):
        if name in existing:
            op.drop_column("market_samples", name)

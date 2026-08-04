"""market sample provenance fields + Tier-3 layer registration

Revision ID: 0008_market_pipeline
Revises: 0007_fct_security_tenure_seed
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_market_pipeline"
down_revision = "0007_fct_security_tenure_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("market_samples")}
    if "sample_type" not in columns:
        op.add_column(
            "market_samples",
            sa.Column(
                "sample_type",
                sa.String(length=16),
                nullable=False,
                server_default="listing",
            ),
        )
    if "verified" not in columns:
        op.add_column(
            "market_samples",
            sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "layer_version" not in columns:
        op.add_column(
            "market_samples",
            sa.Column(
                "layer_version",
                sa.String(length=20),
                nullable=False,
                server_default="unpublished",
            ),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_market_samples_layer_version "
        "ON market_samples (layer_version)"
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO layer_registry (layer, version, source, notes, updated_at)
            VALUES (
              'market', 'unpublished', 'Partner agent network',
              'Tier 3 geocoded listing/transaction samples; publish only after QA', now()
            )
            ON CONFLICT (layer) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM layer_registry WHERE layer = 'market'"))
    op.execute("DROP INDEX IF EXISTS ix_market_samples_layer_version")
    columns = {c["name"] for c in sa.inspect(bind).get_columns("market_samples")}
    for column in ("layer_version", "verified", "sample_type"):
        if column in columns:
            op.drop_column("market_samples", column)

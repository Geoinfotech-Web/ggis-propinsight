"""Geography indexes for radius-based terrain and project queries.

Revision ID: 0015_spatial_query_indexes
Revises: 0014_livability_outlook
Create Date: 2026-08-10
"""
from __future__ import annotations

from alembic import op

revision = "0015_spatial_query_indexes"
down_revision = "0014_livability_outlook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_dem_samples_geography "
        "ON dem_samples USING gist ((geom::geography))"
    )
    op.execute(
        "CREATE INDEX ix_development_projects_geography "
        "ON development_projects USING gist ((geom::geography)) "
        "WHERE geom IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_development_projects_geography", table_name="development_projects")
    op.drop_index("ix_dem_samples_geography", table_name="dem_samples")

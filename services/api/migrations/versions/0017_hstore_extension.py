"""Enable hstore for the OSM osm2pgsql staging pipeline.

Revision ID: 0017_hstore_extension
Revises: 0016_professional_3d_context
Create Date: 2026-08-14
"""
from __future__ import annotations

from alembic import op

revision = "0017_hstore_extension"
down_revision = "0016_professional_3d_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS hstore")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS hstore")

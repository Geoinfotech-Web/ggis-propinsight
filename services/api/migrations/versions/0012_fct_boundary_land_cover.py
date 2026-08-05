"""FCT operational boundary and wall-to-wall observed land cover

Revision ID: 0012_fct_boundary_land_cover
Revises: 0011_land_use_context
Create Date: 2026-08-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision = "0012_fct_boundary_land_cover"
down_revision = "0011_land_use_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "territory_boundaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_version", sa.String(40)),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_territory_boundaries_geom",
        "territory_boundaries",
        ["geom"],
        postgresql_using="gist",
    )

    op.create_table(
        "land_cover_rasters",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("raster_path", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date()),
        sa.Column("period_end", sa.Date()),
        sa.Column("resolution_m", sa.Integer(), nullable=False),
        sa.Column("classes", JSONB(), nullable=False),
        sa.Column("layer_version", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_land_cover_rasters_layer_version",
        "land_cover_rasters",
        ["layer_version"],
    )
    op.execute(
        """
        INSERT INTO layer_registry (layer, version, source, notes, updated_at)
        VALUES (
          'land_cover', 'unpublished', 'Dynamic World / ESA WorldCover',
          'Wall-to-wall observed land cover; not statutory zoning', NOW()
        )
        ON CONFLICT (layer) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM layer_registry WHERE layer = 'land_cover'")
    op.drop_table("land_cover_rasters")
    op.drop_table("territory_boundaries")

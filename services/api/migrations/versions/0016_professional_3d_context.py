"""Overture buildings and observed vegetation canopy for professional 3D.

Revision ID: 0016_professional_3d_context
Revises: 0015_spatial_query_indexes
Create Date: 2026-08-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016_professional_3d_context"
down_revision = "0015_spatial_query_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "building_footprints",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(80), nullable=False, unique=True),
        sa.Column("parent_source_id", sa.String(80)),
        sa.Column("feature_type", sa.String(24), nullable=False),
        sa.Column("building_class", sa.String(80)),
        sa.Column("height_m", sa.Float()),
        sa.Column("num_floors", sa.Integer()),
        sa.Column("min_height_m", sa.Float()),
        sa.Column("display_height_m", sa.Float(), nullable=False),
        sa.Column("height_basis", sa.String(24), nullable=False),
        sa.Column("source_datasets", JSONB(), nullable=False, server_default="[]"),
        sa.Column("release", sa.String(32), nullable=False),
        sa.Column("layer_version", sa.String(32), nullable=False),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
    )
    for column in ("source_id", "parent_source_id", "height_basis", "layer_version"):
        op.create_index(f"ix_building_footprints_{column}", "building_footprints", [column])
    op.create_index(
        "ix_building_footprints_geom",
        "building_footprints",
        ["geom"],
        postgresql_using="gist",
    )

    op.create_table(
        "vegetation_canopy_areas",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("period_start", sa.Date()),
        sa.Column("period_end", sa.Date()),
        sa.Column("resolution_m", sa.Integer(), nullable=False),
        sa.Column("area_ha", sa.Float(), nullable=False),
        sa.Column("layer_version", sa.String(32), nullable=False),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
    )
    op.create_index(
        "ix_vegetation_canopy_areas_layer_version",
        "vegetation_canopy_areas",
        ["layer_version"],
    )
    op.create_index(
        "ix_vegetation_canopy_areas_geom",
        "vegetation_canopy_areas",
        ["geom"],
        postgresql_using="gist",
    )

    for layer, source in (
        ("buildings_3d", "Overture Maps Buildings"),
        ("vegetation_3d", "Published observed land cover"),
    ):
        op.execute(
            sa.text(
                """
                INSERT INTO layer_registry (layer, version, source, notes, updated_at)
                VALUES (:layer, 'unpublished', :source, 'Awaiting 3D context publication', NOW())
                ON CONFLICT (layer) DO NOTHING
                """
            ).bindparams(layer=layer, source=source)
        )


def downgrade() -> None:
    op.execute("DELETE FROM layer_registry WHERE layer IN ('buildings_3d', 'vegetation_3d')")
    op.drop_table("vegetation_canopy_areas")
    op.drop_table("building_footprints")

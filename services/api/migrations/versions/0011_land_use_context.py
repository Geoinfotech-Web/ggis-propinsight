"""open land-use context polygons

Revision ID: 0011_land_use_context
Revises: 0010_merge_market_security
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0011_land_use_context"
down_revision = "0010_merge_market_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "land_use_areas",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("source_class", sa.String(80)),
        sa.Column("source_subtype", sa.String(80)),
        sa.Column("name", sa.String(240)),
        sa.Column("designation", sa.String(32), nullable=False),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("layer_version", sa.String(20), nullable=False),
        sa.UniqueConstraint("source_id", name="uq_land_use_source_id"),
    )
    op.create_index("ix_land_use_geom", "land_use_areas", ["geom"], postgresql_using="gist")
    for column in ("source_id", "category", "designation", "layer_version"):
        op.create_index(f"ix_land_use_areas_{column}", "land_use_areas", [column])
    op.execute(
        """
        INSERT INTO layer_registry (layer, version, source, notes, updated_at)
        VALUES (
          'land_use', 'unpublished', 'Overture Maps / OpenStreetMap',
          'Open reference land use; not statutory AGIS zoning', NOW()
        )
        ON CONFLICT (layer) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM layer_registry WHERE layer = 'land_use'")
    op.drop_table("land_use_areas")

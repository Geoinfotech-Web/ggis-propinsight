"""Ward boundaries and optional ward-level security aggregates.

Revision ID: 0013_ward_security_context
Revises: 0012_fct_boundary_land_cover
Create Date: 2026-08-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0013_ward_security_context"
down_revision = "0012_fct_boundary_land_cover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("area_council", sa.String(160), nullable=False),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_version", sa.String(40)),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_wards_name", "wards", ["name"])
    op.create_index("ix_wards_area_council", "wards", ["area_council"])
    op.create_index("ix_wards_geom", "wards", ["geom"], postgresql_using="gist")

    op.add_column("incidents_agg", sa.Column("ward_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_incidents_agg_ward_id",
        "incidents_agg",
        "wards",
        ["ward_id"],
        ["id"],
    )
    op.create_index("ix_incidents_agg_ward_id", "incidents_agg", ["ward_id"])

    op.execute(
        """
        INSERT INTO layer_registry (layer, version, source, notes, updated_at)
        VALUES (
          'administrative_boundaries', 'unpublished', 'GRID3 operational wards',
          'FCT ward lookup for local context; not a cadastral boundary', NOW()
        )
        ON CONFLICT (layer) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM layer_registry WHERE layer = 'administrative_boundaries'")
    op.drop_index("ix_incidents_agg_ward_id", table_name="incidents_agg")
    op.drop_constraint("fk_incidents_agg_ward_id", "incidents_agg", type_="foreignkey")
    op.drop_column("incidents_agg", "ward_id")
    op.drop_table("wards")

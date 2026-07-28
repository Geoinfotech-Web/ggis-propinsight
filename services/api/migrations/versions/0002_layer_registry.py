"""layer_registry table + seed initial layer versions

Revision ID: 0002_layer_registry
Revises: 0001_initial
Create Date: 2026-07-28

Idempotent: migration 0001 builds the schema via ``Base.metadata.create_all``,
which already includes ``layer_registry`` (the model was added in this revision's
codebase). So here we create the table only if absent and seed it only if empty.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_layer_registry"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


# Layers tracked from the start (Phase 1). Versions bump as ETL publishes them.
# "unpublished" marks a layer whose pipeline has not yet produced data.
SEED_LAYERS = [
    {"layer": "poi", "version": "unpublished", "source": "OSM + agency registries"},
    {"layer": "roads", "version": "unpublished", "source": "OSM (Geofabrik)"},
    {"layer": "dem", "version": "unpublished", "source": "Copernicus/SRTM DEM"},
    {"layer": "hazard", "version": "unpublished", "source": "GGIS Flood Watch mirror"},
    {"layer": "planning", "version": "unpublished", "source": "AGIS / state GIS"},
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "layer_registry" not in inspector.get_table_names():
        op.create_table(
            "layer_registry",
            sa.Column("layer", sa.String(length=32), primary_key=True),
            sa.Column("version", sa.String(length=32), nullable=False),
            sa.Column("source", sa.String(length=120), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    existing = bind.execute(sa.text("SELECT COUNT(*) FROM layer_registry")).scalar()
    if not existing:
        registry = sa.table(
            "layer_registry",
            sa.column("layer", sa.String),
            sa.column("version", sa.String),
            sa.column("source", sa.String),
        )
        op.bulk_insert(registry, SEED_LAYERS)


def downgrade() -> None:
    op.drop_table("layer_registry")

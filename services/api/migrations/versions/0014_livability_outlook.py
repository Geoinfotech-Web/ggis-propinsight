"""Environmental metrics, detailed terrain, and official development projects.

Revision ID: 0014_livability_outlook
Revises: 0013_ward_security_context
Create Date: 2026-08-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision = "0014_livability_outlook"
down_revision = "0013_ward_security_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dem_samples", sa.Column("flow_accumulation", sa.Float()))
    op.add_column("dem_samples", sa.Column("contributing_area_km2", sa.Float()))

    op.create_table(
        "analysis_rasters",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("metric", sa.String(48), nullable=False),
        sa.Column("epoch", sa.String(32)),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("raster_path", sa.Text(), nullable=False),
        sa.Column("resolution_m", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("licence", sa.String(160)),
        sa.Column("layer_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_analysis_rasters_metric", "analysis_rasters", ["metric"])
    op.create_index("ix_analysis_rasters_epoch", "analysis_rasters", ["epoch"])
    op.create_index(
        "ix_analysis_rasters_layer_version", "analysis_rasters", ["layer_version"]
    )

    op.create_table(
        "spatial_metric_cells",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cell_id", sa.String(48), nullable=False, unique=True),
        sa.Column("geom", Geometry("POLYGON", srid=4326), nullable=False),
        sa.Column("population_2025", sa.Float()),
        sa.Column("population_2030", sa.Float()),
        sa.Column("population_growth_percentile", sa.Float()),
        sa.Column("built_share_current", sa.Float()),
        sa.Column("built_change_pct", sa.Float()),
        sa.Column("settlement_growth_percentile", sa.Float()),
        sa.Column("green_share", sa.Float()),
        sa.Column("built_bare_share", sa.Float()),
        sa.Column("surface_temp_c", sa.Float()),
        sa.Column("heat_percentile", sa.Float()),
        sa.Column("layer_versions", JSONB(), server_default="{}"),
        sa.Column("data_period", sa.String(80)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_spatial_metric_cells_cell_id", "spatial_metric_cells", ["cell_id"])
    op.create_index(
        "ix_spatial_metric_cells_geom",
        "spatial_metric_cells",
        ["geom"],
        postgresql_using="gist",
    )

    op.create_table(
        "development_projects",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("official_id", sa.String(160), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("authority", sa.String(160), nullable=False),
        sa.Column("agency", sa.String(200)),
        sa.Column("sector", sa.String(80), nullable=False),
        sa.Column("lifecycle_stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(120)),
        sa.Column("budget_ngn", sa.Float()),
        sa.Column("location_text", sa.Text(), nullable=False),
        sa.Column("ward", sa.String(160)),
        sa.Column("area_council", sa.String(160)),
        sa.Column("geom", Geometry(srid=4326)),
        sa.Column("location_precision", sa.String(32), nullable=False),
        sa.Column("geocoding_confidence", sa.Float()),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_published_at", sa.Date(), nullable=False),
        sa.Column("source_updated_at", sa.Date()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("layer_version", sa.String(32), nullable=False),
    )
    for column in (
        "official_id", "sector", "lifecycle_stage", "ward", "area_council",
        "location_precision", "active", "layer_version",
    ):
        op.create_index(f"ix_development_projects_{column}", "development_projects", [column])
    op.create_index(
        "ix_development_projects_geom",
        "development_projects",
        ["geom"],
        postgresql_using="gist",
    )

    for layer, source in (
        ("surface_heat", "USGS Landsat Collection 2 Level-2"),
        ("population", "European Commission GHSL P2023A via Earth Engine"),
        ("settlement", "European Commission GHSL"),
        ("projects", "FCTA + NOCOPO + Federal Budget Office"),
    ):
        op.execute(
            sa.text(
                """
                INSERT INTO layer_registry (layer, version, source, notes, updated_at)
                VALUES (:layer, 'unpublished', :source, 'Awaiting verified ETL publication', NOW())
                ON CONFLICT (layer) DO NOTHING
                """
            ).bindparams(layer=layer, source=source)
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM layer_registry WHERE layer IN "
        "('surface_heat', 'population', 'settlement', 'projects')"
    )
    op.drop_table("development_projects")
    op.drop_table("spatial_metric_cells")
    op.drop_table("analysis_rasters")
    op.drop_column("dem_samples", "contributing_area_km2")
    op.drop_column("dem_samples", "flow_accumulation")

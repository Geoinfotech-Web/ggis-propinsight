"""Nationwide state readiness and admin GIS upload batches.

Revision ID: 0018_national_admin_gis
Revises: 0017_hstore_extension
Create Date: 2026-09-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

from app.nigeria_states import NIGERIA_STATES

revision = "0018_national_admin_gis"
down_revision = "0017_hstore_extension"
branch_labels = None
depends_on = None

STATE_LAYERS = (
    "admin_boundaries",
    "masterplan",
    "poi",
    "roads",
    "dem",
    "land_cover",
    "security",
    "market",
    "projects",
    "buildings_3d",
    "vegetation_3d",
)


def upgrade() -> None:
    op.create_table(
        "states",
        sa.Column("code", sa.String(8), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("capital", sa.String(120)),
        sa.Column("centroid_lon", sa.Float(), nullable=False),
        sa.Column("centroid_lat", sa.Float(), nullable=False),
        sa.Column("bbox", JSONB(), nullable=False, server_default="[]"),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_version", sa.String(40)),
        sa.Column("readiness", sa.String(24), nullable=False, server_default="setup_required"),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_states_name", "states", ["name"])
    op.create_index("ix_states_published", "states", ["published"])
    op.create_index("ix_states_readiness", "states", ["readiness"])
    op.create_index("ix_states_geom", "states", ["geom"], postgresql_using="gist")

    op.create_table(
        "lgas",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(120), nullable=False, unique=True),
        sa.Column("state_code", sa.String(8), sa.ForeignKey("states.code"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_version", sa.String(40)),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("source_id", "state_code", "name"):
        op.create_index(f"ix_lgas_{column}", "lgas", [column])
    op.create_index("ix_lgas_geom", "lgas", ["geom"], postgresql_using="gist")

    op.add_column("wards", sa.Column("state_code", sa.String(8), nullable=True))
    op.add_column("wards", sa.Column("lga_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_wards_state_code", "wards", "states", ["state_code"], ["code"])
    op.create_foreign_key("fk_wards_lga_id", "wards", "lgas", ["lga_id"], ["id"])
    op.create_index("ix_wards_state_code", "wards", ["state_code"])
    op.create_index("ix_wards_lga_id", "wards", ["lga_id"])

    op.create_table(
        "masterplan_areas",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(160), nullable=False, unique=True),
        sa.Column("state_code", sa.String(8), sa.ForeignKey("states.code"), nullable=False),
        sa.Column("lga_id", sa.BigInteger(), sa.ForeignKey("lgas.id")),
        sa.Column("plan_name", sa.String(240)),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("source_class", sa.String(120)),
        sa.Column("source_doc", sa.String(240)),
        sa.Column("effective_date", sa.Date()),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("layer_version", sa.String(32), nullable=False),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("source_id", "state_code", "lga_id", "category", "layer_version"):
        op.create_index(f"ix_masterplan_areas_{column}", "masterplan_areas", [column])
    op.create_index("ix_masterplan_areas_geom", "masterplan_areas", ["geom"], postgresql_using="gist")

    op.create_table(
        "state_layer_registry",
        sa.Column("state_code", sa.String(8), sa.ForeignKey("states.code"), primary_key=True),
        sa.Column("layer", sa.String(32), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="unpublished"),
        sa.Column("status", sa.String(24), nullable=False, server_default="unpublished"),
        sa.Column("source", sa.String(160)),
        sa.Column("notes", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_state_layer_registry_status", "state_layer_registry", ["status"])

    op.create_table(
        "gis_upload_batches",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("target_layer", sa.String(32), nullable=False),
        sa.Column("state_code", sa.String(8)),
        sa.Column("file_name", sa.String(260), nullable=False),
        sa.Column("file_type", sa.String(24), nullable=False),
        sa.Column("source_name", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("license_note", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("validation_report", JSONB(), nullable=False, server_default="{}"),
        sa.Column("attribute_mapping", JSONB(), nullable=False, server_default="{}"),
        sa.Column("feature_collection", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    for column in ("target_layer", "state_code", "status"):
        op.create_index(f"ix_gis_upload_batches_{column}", "gis_upload_batches", [column])

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(80)),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("action", "target_type", "target_id"):
        op.create_index(f"ix_admin_audit_log_{column}", "admin_audit_log", [column])

    bind = op.get_bind()
    for state in NIGERIA_STATES:
        bbox = state["bbox"]
        centroid = state["centroid"]
        readiness = "ready" if state["code"] == "FC" else "setup_required"
        bind.execute(
            sa.text(
                """
                INSERT INTO states (
                  code, name, capital, centroid_lon, centroid_lat, bbox,
                  published, source, source_version, readiness, geom, updated_at
                )
                VALUES (
                  :code, :name, :capital, :centroid_lon, :centroid_lat,
                  CAST(:bbox AS jsonb), :published, :source, :source_version,
                  :readiness,
                  ST_Multi(ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)),
                  NOW()
                )
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": state["code"],
                "name": state["name"],
                "capital": state["capital"],
                "centroid_lon": centroid[0],
                "centroid_lat": centroid[1],
                "bbox": str(bbox).replace("'", '"'),
                "published": state["code"] == "FC",
                "source": "PropInsight operational state seed",
                "source_version": "2026.09.seed",
                "readiness": readiness,
                "min_lon": bbox[0],
                "min_lat": bbox[1],
                "max_lon": bbox[2],
                "max_lat": bbox[3],
            },
        )
        for layer in STATE_LAYERS:
            is_fct_ready = state["code"] == "FC" and layer in {
                "admin_boundaries", "poi", "roads", "dem", "land_cover", "security",
                "market", "masterplan", "projects", "buildings_3d", "vegetation_3d",
            }
            bind.execute(
                sa.text(
                    """
                    INSERT INTO state_layer_registry (
                      state_code, layer, version, status, source, notes, updated_at
                    )
                    VALUES (:state_code, :layer, :version, :status, :source, :notes, NOW())
                    ON CONFLICT (state_code, layer) DO NOTHING
                    """
                ),
                {
                    "state_code": state["code"],
                    "layer": layer,
                    "version": "2026.09.seed" if is_fct_ready else "unpublished",
                    "status": "published" if is_fct_ready else "unpublished",
                    "source": "Existing FCT pilot layers" if is_fct_ready else None,
                    "notes": None if is_fct_ready else "Awaiting admin upload or ETL publish",
                },
            )

    op.execute(
        """
        UPDATE wards
        SET state_code = 'FC'
        WHERE state_code IS NULL
          AND (state ILIKE '%fct%' OR state ILIKE '%abuja%' OR state ILIKE '%federal capital%')
        """
    )


def downgrade() -> None:
    op.drop_table("admin_audit_log")
    op.drop_table("gis_upload_batches")
    op.drop_table("state_layer_registry")
    op.drop_table("masterplan_areas")
    op.drop_index("ix_wards_lga_id", table_name="wards")
    op.drop_index("ix_wards_state_code", table_name="wards")
    op.drop_constraint("fk_wards_lga_id", "wards", type_="foreignkey")
    op.drop_constraint("fk_wards_state_code", "wards", type_="foreignkey")
    op.drop_column("wards", "lga_id")
    op.drop_column("wards", "state_code")
    op.drop_table("lgas")
    op.drop_table("states")

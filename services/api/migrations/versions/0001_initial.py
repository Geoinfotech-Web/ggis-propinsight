"""schema v1 (TDD §6.1) + PostGIS extension + fct-v1 scoring profiles

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-28
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

from app.db import Base
from app import models  # noqa: F401 — registers tables on Base.metadata

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


# fct-v1 weights per domain (Σ w_i = 1). Published on the methodology page.
FCT_V1_PROFILES: dict[str, dict[str, float]] = {
    "flood": {"ggis_risk": 1.0},
    "amenities": {
        "school": 0.20, "hospital": 0.20, "water": 0.15,
        "power": 0.15, "isp": 0.10, "market": 0.10, "bank": 0.05, "fuel": 0.05,
    },
    "accessibility": {
        "road_distance": 0.30, "cbd_time": 0.25, "airport_time": 0.15,
        "market_time": 0.15, "rainy_season": 0.15,
    },
    "feasibility": {
        "slope": 0.30, "flood": 0.25, "utility_distance": 0.25, "catchment": 0.20,
    },
    "security": {"incident_rate": 0.6, "police_proximity": 0.4},
    "tenure": {"acquisition_overlap": 0.5, "layout_approval": 0.3, "setback": 0.2},
    "market": {"price_level": 0.5, "trend": 0.3, "yield": 0.2},
    "livability": {"reviews": 0.6, "density": 0.4},
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    # Seed the FCT pilot scoring profile (fct-v1).
    profiles = sa.table(
        "scoring_profiles",
        sa.column("profile_key", sa.String),
        sa.column("domain", sa.String),
        sa.column("weights", sa.JSON),
        sa.column("normalisation", sa.JSON),
    )
    op.bulk_insert(
        profiles,
        [
            {
                "profile_key": "fct-v1",
                "domain": domain,
                "weights": json.dumps(weights),
                "normalisation": json.dumps({}),
            }
            for domain, weights in FCT_V1_PROFILES.items()
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

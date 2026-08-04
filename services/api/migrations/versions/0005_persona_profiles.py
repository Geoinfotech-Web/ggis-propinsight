"""Seed persona scoring profiles (domain-level weights).

Revision ID: 0005_persona_profiles
Revises: 0004_fct_named_pois
Create Date: 2026-07-30

Adds home_buyer / investor / tenant / developer rows to scoring_profiles.
Indicator weights mirror fct-v1; domain-level importance is stored under
normalisation.domain_weights for auditability.
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0005_persona_profiles"
down_revision = "0004_fct_named_pois"
branch_labels = None
depends_on = None

# Indicator weights (same as fct-v1) — methodology unchanged inside each domain.
FCT_V1_INDICATORS: dict[str, dict[str, float]] = {
    "flood": {"ggis_risk": 1.0},
    "amenities": {
        "school": 0.20,
        "hospital": 0.20,
        "water": 0.15,
        "power": 0.15,
        "isp": 0.10,
        "market": 0.10,
        "bank": 0.05,
        "fuel": 0.05,
    },
    "accessibility": {
        "road_distance": 0.30,
        "cbd_time": 0.25,
        "airport_time": 0.15,
        "market_time": 0.15,
        "rainy_season": 0.15,
    },
    "feasibility": {
        "slope": 0.30,
        "flood": 0.25,
        "utility_distance": 0.25,
        "catchment": 0.20,
    },
    "security": {"incident_rate": 0.6, "police_proximity": 0.4},
    "tenure": {"acquisition_overlap": 0.5, "layout_approval": 0.3, "setback": 0.2},
    "market": {"price_level": 0.5, "trend": 0.3, "yield": 0.2},
    "livability": {"reviews": 0.6, "density": 0.4},
}

PERSONA_DOMAIN_WEIGHTS: dict[str, dict[str, float]] = {
    "home_buyer": {
        "flood": 0.20,
        "amenities": 0.20,
        "security": 0.15,
        "accessibility": 0.15,
        "livability": 0.10,
        "tenure": 0.08,
        "market": 0.07,
        "feasibility": 0.05,
    },
    "investor": {
        "market": 0.25,
        "security": 0.15,
        "flood": 0.15,
        "tenure": 0.15,
        "accessibility": 0.10,
        "amenities": 0.08,
        "feasibility": 0.07,
        "livability": 0.05,
    },
    "tenant": {
        "amenities": 0.22,
        "security": 0.20,
        "flood": 0.15,
        "accessibility": 0.15,
        "livability": 0.15,
        "market": 0.08,
        "tenure": 0.03,
        "feasibility": 0.02,
    },
    "developer": {
        "feasibility": 0.23,
        "tenure": 0.20,
        "flood": 0.15,
        "accessibility": 0.12,
        "market": 0.10,
        "security": 0.10,
        "amenities": 0.05,
        "livability": 0.05,
    },
}


def upgrade() -> None:
    bind = op.get_bind()
    profiles = sa.table(
        "scoring_profiles",
        sa.column("profile_key", sa.String),
        sa.column("domain", sa.String),
        sa.column("weights", sa.JSON),
        sa.column("normalisation", sa.JSON),
    )

    # Idempotent: remove prior persona rows then re-insert.
    bind.execute(
        sa.text(
            "DELETE FROM scoring_profiles WHERE profile_key IN "
            "('home_buyer', 'investor', 'tenant', 'developer')"
        )
    )

    rows = []
    for persona_key, domain_weights in PERSONA_DOMAIN_WEIGHTS.items():
        for domain, indicators in FCT_V1_INDICATORS.items():
            rows.append(
                {
                    "profile_key": persona_key,
                    "domain": domain,
                    "weights": json.dumps(indicators),
                    "normalisation": json.dumps(
                        {
                            "domain_weight": domain_weights.get(domain, 0.0),
                            "persona": persona_key,
                        }
                    ),
                }
            )
    op.bulk_insert(profiles, rows)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM scoring_profiles WHERE profile_key IN "
            "('home_buyer', 'investor', 'tenant', 'developer')"
        )
    )

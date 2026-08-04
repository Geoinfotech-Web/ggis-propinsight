"""Exclude feasibility from home_buyer / tenant persona weights.

Revision ID: 0006_persona_domain_exclusions
Revises: 0005_persona_profiles
Create Date: 2026-07-30

Runtime personas.py is authoritative for fit/priority. This migration updates
scoring_profiles rows so DB config matches: no feasibility weight for
home_buyer and tenant; remaining domain_weights renormalised.
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0006_persona_domain_exclusions"
down_revision = "0005_persona_profiles"
branch_labels = None
depends_on = None

# Updated domain-level weights (feasibility omitted for buyer/tenant).
PERSONA_DOMAIN_WEIGHTS: dict[str, dict[str, float]] = {
    "home_buyer": {
        "flood": 0.21,
        "amenities": 0.21,
        "security": 0.16,
        "accessibility": 0.16,
        "livability": 0.10,
        "tenure": 0.09,
        "market": 0.07,
    },
    "tenant": {
        "amenities": 0.22,
        "security": 0.21,
        "flood": 0.15,
        "accessibility": 0.15,
        "livability": 0.15,
        "market": 0.09,
        "tenure": 0.03,
    },
}


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, profile_key, domain, normalisation FROM scoring_profiles "
            "WHERE profile_key IN ('home_buyer', 'tenant')"
        )
    ).mappings().all()

    for row in rows:
        persona = row["profile_key"]
        domain = row["domain"]
        weights = PERSONA_DOMAIN_WEIGHTS[persona]
        raw = row["normalisation"]
        if isinstance(raw, str):
            norm = json.loads(raw)
        elif raw is None:
            norm = {}
        else:
            norm = dict(raw)

        if domain == "feasibility" or domain not in weights:
            norm["domain_weight"] = None
            norm["excluded"] = True
        else:
            norm["domain_weight"] = weights[domain]
            norm.pop("excluded", None)

        bind.execute(
            sa.text(
                "UPDATE scoring_profiles SET normalisation = CAST(:norm AS jsonb) WHERE id = :id"
            ),
            {"norm": json.dumps(norm), "id": row["id"]},
        )


def downgrade() -> None:
    # Restore previous buyer/tenant feasibility weights from 0005 values.
    previous = {
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
    }
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, profile_key, domain, normalisation FROM scoring_profiles "
            "WHERE profile_key IN ('home_buyer', 'tenant')"
        )
    ).mappings().all()
    for row in rows:
        persona = row["profile_key"]
        domain = row["domain"]
        weights = previous[persona]
        raw = row["normalisation"]
        if isinstance(raw, str):
            norm = json.loads(raw)
        elif raw is None:
            norm = {}
        else:
            norm = dict(raw)
        norm["domain_weight"] = weights.get(domain, 0.0)
        norm.pop("excluded", None)
        bind.execute(
            sa.text(
                "UPDATE scoring_profiles SET normalisation = CAST(:norm AS jsonb) WHERE id = :id"
            ),
            {"norm": json.dumps(norm), "id": row["id"]},
        )

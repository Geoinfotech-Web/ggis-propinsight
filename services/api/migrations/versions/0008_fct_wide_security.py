"""FCT-wide security coverage: Area Councils + territory fallback + incidents

Revision ID: 0008_fct_wide_security
Revises: 0007_fct_security_tenure_seed
Create Date: 2026-08-04

Adds the six FCT Area Councils plus a territory-wide fallback district (each with
incident aggregates) so every point in the FCT resolves to a district and the
security domain scores instead of degrading. `district_for_point` prefers the
smallest containing district, so the detailed Central-Area districts still win
where they exist. Idempotent: skips if Area Councils are already seeded.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_fct_wide_security"
down_revision = "0007_fct_security_tenure_seed"
branch_labels = None
depends_on = None

# (id, name, density, xmin, ymin, xmax, ymax) — Area Councils tiling the FCT,
# plus a whole-territory fallback (largest area => lowest resolution priority).
DISTRICTS = [
    (6, "Abuja Municipal (AMAC)", "high", 7.35, 8.95, 7.65, 9.20),
    (7, "Bwari", "medium", 7.30, 9.15, 7.72, 9.40),
    (8, "Gwagwalada", "medium", 6.90, 8.75, 7.35, 9.10),
    (9, "Kuje", "low", 7.05, 8.65, 7.50, 9.00),
    (10, "Abaji", "low", 6.75, 8.25, 7.25, 8.75),
    (11, "Kwali", "low", 6.85, 8.55, 7.30, 8.95),
    (12, "Federal Capital Territory", "medium", 6.75, 8.25, 7.75, 9.35),  # fallback
]

# (district_id, category, count) for period 2026-Q2.
INCIDENTS = [
    (6, "theft", 20), (6, "burglary", 9), (6, "assault", 5),
    (7, "theft", 7), (7, "burglary", 3),
    (8, "theft", 9), (8, "burglary", 4),
    (9, "theft", 4), (9, "burglary", 2),
    (10, "theft", 2), (10, "burglary", 1),
    (11, "theft", 3), (11, "burglary", 1),
    (12, "theft", 10), (12, "burglary", 4),
]

PERIOD = "2026-Q2"


def upgrade() -> None:
    bind = op.get_bind()
    already = bind.execute(
        sa.text("SELECT COUNT(*) FROM districts WHERE id >= 6")
    ).scalar()
    if already:
        return

    for did, name, density, xmin, ymin, xmax, ymax in DISTRICTS:
        bind.execute(
            sa.text(
                """
                INSERT INTO districts (id, name, state, density_class, geom)
                VALUES (:id, :name, 'FCT', :density,
                        ST_Multi(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax, 4326)))
                """
            ),
            {"id": did, "name": name, "density": density,
             "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
        )

    for i, (did, category, count) in enumerate(INCIDENTS, start=100):
        bind.execute(
            sa.text(
                """
                INSERT INTO incidents_agg (id, district_id, period, category, count, source)
                VALUES (:id, :did, :period, :category, :count, 'demo-seed')
                """
            ),
            {"id": i, "did": did, "period": PERIOD, "category": category, "count": count},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM incidents_agg WHERE district_id >= 6"))
    bind.execute(sa.text("DELETE FROM districts WHERE id >= 6"))

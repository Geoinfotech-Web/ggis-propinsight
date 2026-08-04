"""FCT demo seed: districts, incident aggregates, police, planning overlays

Revision ID: 0007_fct_security_tenure_seed
Revises: 0006_persona_domain_exclusions
Create Date: 2026-08-04

Seeds a small Abuja pilot dataset so the security and tenure domains score
locally, and publishes the `security` + `planning` layers. Idempotent: skips if
districts are already present. Live ACLED / AGIS data later simply repopulates
these tables and republishes the layers — no code change (incl. new states).
"""
from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from alembic import op

revision = "0007_fct_security_tenure_seed"
down_revision = "0006_persona_domain_exclusions"
branch_labels = None
depends_on = None

LAYER = "2026.07.demo"

# (id, name, state, density, xmin, ymin, xmax, ymax) — non-overlapping FCT rects.
DISTRICTS = [
    (1, "Central Area", "FCT", "medium", 7.472, 9.045, 7.498, 9.070),
    (2, "Garki", "FCT", "high", 7.485, 9.020, 7.512, 9.043),
    (3, "Wuse", "FCT", "high", 7.458, 9.058, 7.472, 9.090),
    (4, "Maitama", "FCT", "low", 7.478, 9.072, 7.512, 9.105),
    (5, "Asokoro", "FCT", "low", 7.500, 9.030, 7.535, 9.060),
]

# (district_id, period, category, count)
INCIDENTS = [
    (1, "2026-Q2", "theft", 8), (1, "2026-Q2", "burglary", 3),
    (2, "2026-Q2", "theft", 12), (2, "2026-Q2", "burglary", 5),
    (3, "2026-Q2", "theft", 15), (3, "2026-Q2", "burglary", 6),
    (4, "2026-Q2", "theft", 3), (4, "2026-Q2", "burglary", 1),
    (5, "2026-Q2", "theft", 2), (5, "2026-Q2", "burglary", 1),
]

# Police / security outposts as POIs (ids well above demo/named POIs).
POLICE = [
    (9001, 7.4880, 9.0560, "Central Police Station Garki"),
    (9002, 7.4700, 9.0720, "Wuse Division Police"),
    (9003, 7.5050, 9.0400, "Asokoro Police Station"),
    (9004, 7.4950, 9.0900, "Maitama Police Station"),
]

# (id, kind, status, source_doc, effective_date, xmin, ymin, xmax, ymax)
PLANNING = [
    (1, "layout", "approved", "AGIS Approved Layout - Central Area", "2019-01-01",
     7.475, 9.050, 7.496, 9.066),
    (2, "acquisition", "under acquisition", "FCDA Acquisition Notice 2021", "2021-06-01",
     7.458, 9.080, 7.472, 9.095),
    (3, "setback", "waterway setback 30m", "Jabi Stream Setback", "2018-01-01",
     7.500, 9.030, 7.506, 9.060),
    (4, "corridor", "132kV transmission corridor", "TCN Corridor", "2015-01-01",
     7.512, 9.045, 7.516, 9.105),
    (5, "greenbelt", "greenbelt reservation", "FCT Green Area", "2010-01-01",
     7.520, 9.090, 7.535, 9.105),
]


def _publish(bind, layer: str, source: str, notes: str) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO layer_registry (layer, version, source, notes, updated_at)
            VALUES (:layer, :ver, :source, :notes, NOW())
            ON CONFLICT (layer) DO UPDATE
              SET version = EXCLUDED.version, source = EXCLUDED.source,
                  notes = EXCLUDED.notes, updated_at = NOW()
            """
        ),
        {"layer": layer, "ver": LAYER, "source": source, "notes": notes},
    )


def upgrade() -> None:
    bind = op.get_bind()

    if bind.execute(sa.text("SELECT COUNT(*) FROM districts")).scalar():
        return  # already seeded

    for did, name, state, density, xmin, ymin, xmax, ymax in DISTRICTS:
        bind.execute(
            sa.text(
                """
                INSERT INTO districts (id, name, state, density_class, geom)
                VALUES (:id, :name, :state, :density,
                        ST_Multi(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax, 4326)))
                """
            ),
            {"id": did, "name": name, "state": state, "density": density,
             "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
        )

    for i, (did, period, category, count) in enumerate(INCIDENTS, start=1):
        bind.execute(
            sa.text(
                """
                INSERT INTO incidents_agg (id, district_id, period, category, count, source)
                VALUES (:id, :did, :period, :category, :count, 'demo-seed')
                """
            ),
            {"id": i, "did": did, "period": period, "category": category, "count": count},
        )

    for pid, lon, lat, name in POLICE:
        bind.execute(
            sa.text(
                """
                INSERT INTO poi (id, geom, category, name, source, verified, layer_version)
                VALUES (:id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                        'police', :name, 'demo-seed', true, :ver)
                """
            ),
            {"id": pid, "lon": lon, "lat": lat, "name": name, "ver": LAYER},
        )

    for pid, kind, status, source_doc, eff, xmin, ymin, xmax, ymax in PLANNING:
        bind.execute(
            sa.text(
                """
                INSERT INTO planning_layers (id, geom, kind, status, source_doc, effective_date)
                VALUES (:id, ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax, 4326),
                        :kind, :status, :source_doc, :eff)
                """
            ),
            {"id": pid, "kind": kind, "status": status, "source_doc": source_doc,
             "eff": date.fromisoformat(eff), "xmin": xmin, "ymin": ymin,
             "xmax": xmax, "ymax": ymax},
        )

    _publish(bind, "security", "demo-seed", "FCT pilot incident aggregates + police")
    _publish(bind, "planning", "demo-seed", "FCT pilot planning overlays (advisory)")


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM poi WHERE category = 'police' AND source = 'demo-seed'"))
    bind.execute(sa.text("DELETE FROM incidents_agg WHERE source = 'demo-seed'"))
    bind.execute(sa.text("DELETE FROM planning_layers WHERE id <= 5"))
    bind.execute(sa.text("DELETE FROM districts WHERE id <= 5"))
    for layer in ("security", "planning"):
        bind.execute(
            sa.text(
                "UPDATE layer_registry SET version = 'unpublished', notes = NULL WHERE layer = :l"
            ),
            {"l": layer},
        )

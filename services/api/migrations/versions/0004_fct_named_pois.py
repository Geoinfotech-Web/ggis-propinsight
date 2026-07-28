"""Replace demo POI placeholders with named FCT amenities.

Revision ID: 0004_fct_named_pois
Revises: 0003_fct_demo_seed
Create Date: 2026-07-28

Swaps source='demo-seed' POIs for well-known Abuja / FCT facilities so the
amenities nearby list shows real names (not Demo Primary School, etc.).
Idempotent: deletes prior demo-seed rows and re-inserts this set.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_fct_named_pois"
down_revision = "0003_fct_demo_seed"
branch_labels = None
depends_on = None

LAYER = "2026.07.fct-named"

# Approximate lon/lat for well-known FCT amenities (pilot seed until OSM ETL).
# (lon, lat, category, name)
FCT_POIS = [
    # Schools
    (7.4952, 9.0355, "school", "Government Secondary School Garki"),
    (7.4685, 9.0648, "school", "Loyola Jesuit College"),
    (7.4905, 9.0452, "school", "Queen's College Abuja"),
    (7.4548, 9.0665, "school", "American International School of Abuja"),
    (7.4880, 9.0585, "school", "Capital Science Academy"),
    (7.5020, 9.0705, "school", "Premier International School Maitama"),
    # Hospitals / clinics
    (7.4917, 9.0425, "hospital", "National Hospital Abuja"),
    (7.4955, 9.0308, "hospital", "Garki Hospital"),
    (7.4950, 9.0855, "hospital", "Maitama District Hospital"),
    (7.4648, 9.0752, "hospital", "Nisa Premier Hospital"),
    (7.4785, 9.0520, "hospital", "Asokoro District Hospital"),
    (7.4865, 9.0615, "hospital", "Cedarcrest Hospitals"),
    # Markets
    (7.4890, 9.0720, "market", "Wuse Market"),
    (7.4955, 9.0348, "market", "Garki International Market"),
    (7.4405, 9.0655, "market", "Utako Market"),
    (7.4580, 9.0485, "market", "Gudu Market"),
    # Banks
    (7.4950, 9.0525, "bank", "Central Bank of Nigeria"),
    (7.4925, 9.0578, "bank", "Zenith Bank Central Area"),
    (7.4885, 9.0695, "bank", "First Bank Wuse II"),
    (7.4810, 9.0555, "bank", "Access Bank Asokoro"),
    (7.5005, 9.0635, "bank", "GTBank Maitama"),
    # Supporting amenities for scoring completeness
    (7.4880, 9.0500, "water", "Area 1 Water Board"),
    (7.4920, 9.0650, "power", "TCN Abuja Transmission Station"),
    (7.4850, 9.0580, "isp", "MainOne Abuja PoP"),
    (7.4800, 9.0450, "fuel", "TotalEnergies Asokoro"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "poi" not in inspector.get_table_names():
        return

    bind.execute(sa.text("DELETE FROM poi WHERE source = 'demo-seed'"))

    for i, (lon, lat, category, name) in enumerate(FCT_POIS, start=1001):
        bind.execute(
            sa.text(
                """
                INSERT INTO poi (id, geom, category, name, source, verified, layer_version)
                VALUES (
                  :id,
                  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :category, :name, 'demo-seed', true, :ver
                )
                ON CONFLICT (id) DO UPDATE SET
                  geom = EXCLUDED.geom,
                  category = EXCLUDED.category,
                  name = EXCLUDED.name,
                  source = EXCLUDED.source,
                  verified = EXCLUDED.verified,
                  layer_version = EXCLUDED.layer_version
                """
            ),
            {
                "id": i,
                "lon": lon,
                "lat": lat,
                "category": category,
                "name": name,
                "ver": LAYER,
            },
        )

    bind.execute(
        sa.text(
            """
            INSERT INTO layer_registry (layer, version, source, notes, updated_at)
            VALUES ('poi', :ver, 'FCT named amenity seed', 'Named schools/hospitals/markets/banks for PropInsight pilot', now())
            ON CONFLICT (layer) DO UPDATE SET
              version = EXCLUDED.version,
              source = EXCLUDED.source,
              notes = EXCLUDED.notes,
              updated_at = now()
            """
        ),
        {"ver": LAYER},
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "poi" not in inspector.get_table_names():
        return
    bind.execute(sa.text("DELETE FROM poi WHERE source = 'demo-seed' AND layer_version = :ver"), {"ver": LAYER})

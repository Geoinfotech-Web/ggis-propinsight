"""FCT demo seed: roads, dem_samples, sample POIs + publish Tier-1 layers

Revision ID: 0003_fct_demo_seed
Revises: 0002_layer_registry
Create Date: 2026-07-28

Seeds a small Abuja pilot dataset so amenities / accessibility / feasibility
can score locally before full OSM/GEE ETL publishes. Idempotent: skips if
demo POIs already present.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0003_fct_demo_seed"
down_revision = "0002_layer_registry"
branch_labels = None
depends_on = None

LAYER = "2026.07.demo"


# (lon, lat, category, name)
DEMO_POIS = [
    (7.4950, 9.0600, "school", "Demo Primary School"),
    (7.5000, 9.0550, "hospital", "Demo Clinic"),
    (7.4880, 9.0500, "water", "Demo Borehole"),
    (7.4920, 9.0650, "power", "Demo Substation"),
    (7.4850, 9.0580, "isp", "Demo Fibre Hub"),
    (7.4890, 9.0720, "market", "Wuse Market (demo)"),
    (7.4980, 9.0620, "bank", "Demo Bank"),
    (7.4800, 9.0450, "fuel", "Demo Filling Station"),
]

# Simple road segments around Central Area (lon/lat pairs).
DEMO_ROADS = [
    ((7.480, 9.055), (7.505, 9.055), "primary", "Demo Ring Road"),
    ((7.491, 9.040), (7.491, 9.075), "secondary", "Demo North-South"),
    ((7.470, 9.060), (7.510, 9.060), "tertiary", "Demo East-West"),
]

# Sparse DEM samples (lon, lat, elevation_m, slope_deg, twi)
DEMO_DEM = [
    (7.4913, 9.0579, 480.0, 3.5, 6.2),
    (7.5000, 9.0500, 460.0, 8.0, 7.5),
    (7.4800, 9.0700, 500.0, 12.0, 9.0),
    (7.4700, 9.0400, 420.0, 18.0, 11.5),
    (7.5100, 9.0650, 490.0, 5.0, 5.5),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "roads" not in tables:
        op.create_table(
            "roads",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("geom", Geometry("LINESTRING", srid=4326), nullable=False),
            sa.Column("highway", sa.String(40)),
            sa.Column("name", sa.String(200)),
            sa.Column("layer_version", sa.String(20), nullable=False),
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_roads_geom ON roads USING GIST (geom)")

    if "dem_samples" not in tables:
        op.create_table(
            "dem_samples",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("geom", Geometry("POINT", srid=4326), nullable=False),
            sa.Column("elevation_m", sa.Float(), nullable=False),
            sa.Column("slope_deg", sa.Float(), nullable=False),
            sa.Column("twi", sa.Float(), nullable=False),
            sa.Column("layer_version", sa.String(20), nullable=False),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_dem_samples_geom ON dem_samples USING GIST (geom)"
        )

    # Seed only once (detect by demo POI name).
    already = bind.execute(
        sa.text("SELECT COUNT(*) FROM poi WHERE name = :n"),
        {"n": "Demo Primary School"},
    ).scalar()
    if already:
        return

    for i, (lon, lat, category, name) in enumerate(DEMO_POIS, start=1):
        bind.execute(
            sa.text(
                """
                INSERT INTO poi (id, geom, category, name, source, verified, layer_version)
                VALUES (
                  :id,
                  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :category, :name, 'demo-seed', true, :ver
                )
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

    for i, (a, b, highway, name) in enumerate(DEMO_ROADS, start=1):
        bind.execute(
            sa.text(
                """
                INSERT INTO roads (id, geom, highway, name, layer_version)
                VALUES (
                  :id,
                  ST_SetSRID(
                    ST_MakeLine(ST_MakePoint(:lon1, :lat1), ST_MakePoint(:lon2, :lat2)),
                    4326
                  ),
                  :highway, :name, :ver
                )
                """
            ),
            {
                "id": i,
                "lon1": a[0],
                "lat1": a[1],
                "lon2": b[0],
                "lat2": b[1],
                "highway": highway,
                "name": name,
                "ver": LAYER,
            },
        )

    for i, (lon, lat, elev, slope, twi) in enumerate(DEMO_DEM, start=1):
        bind.execute(
            sa.text(
                """
                INSERT INTO dem_samples (id, geom, elevation_m, slope_deg, twi, layer_version)
                VALUES (
                  :id,
                  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :elev, :slope, :twi, :ver
                )
                """
            ),
            {
                "id": i,
                "lon": lon,
                "lat": lat,
                "elev": elev,
                "slope": slope,
                "twi": twi,
                "ver": LAYER,
            },
        )

    # Publish Tier-1 layers so analyze can score them.
    for layer, source, notes in (
        ("poi", "demo-seed", "FCT pilot demo POIs"),
        ("roads", "demo-seed", "FCT pilot demo road centrelines"),
        ("dem", "demo-seed", "FCT pilot DEM point samples"),
    ):
        bind.execute(
            sa.text(
                """
                INSERT INTO layer_registry (layer, version, source, notes, updated_at)
                VALUES (:layer, :ver, :source, :notes, NOW())
                ON CONFLICT (layer) DO UPDATE
                  SET version = EXCLUDED.version,
                      source = EXCLUDED.source,
                      notes = EXCLUDED.notes,
                      updated_at = NOW()
                """
            ),
            {"layer": layer, "ver": LAYER, "source": source, "notes": notes},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM poi WHERE source = 'demo-seed'"))
    bind.execute(sa.text("DELETE FROM roads WHERE layer_version = :v"), {"v": LAYER})
    bind.execute(sa.text("DELETE FROM dem_samples WHERE layer_version = :v"), {"v": LAYER})
    for layer in ("poi", "roads", "dem"):
        bind.execute(
            sa.text(
                "UPDATE layer_registry SET version = 'unpublished', notes = NULL WHERE layer = :l"
            ),
            {"l": layer},
        )
    op.drop_table("dem_samples")
    op.drop_table("roads")

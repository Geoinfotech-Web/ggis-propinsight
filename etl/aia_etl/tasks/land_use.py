"""Publish open land-use context separately from statutory planning overlays."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer, next_layer_version
from aia_etl.sources.base import FCT_BBOX
from aia_etl.sources.overture_land_use import (
    DESIGNATION,
    SOURCE_NAME,
    SOURCE_URL,
    fetch_overture_land_use,
)
from aia_etl.tasks.boundaries import refresh_fct_boundary

log = logging.getLogger(__name__)
settings = get_settings()


@app.task(name="aia_etl.tasks.land_use.refresh_land_use")
def refresh_land_use(bbox: list[float] | None = None) -> dict[str, Any]:
    """Refresh FCT open land use; never present it as official AGIS zoning."""
    refresh_fct_boundary.run()
    aoi = tuple(bbox) if bbox else FCT_BBOX
    records, release = fetch_overture_land_use(aoi, settings.overture_release)  # type: ignore[arg-type]
    if not records:
        raise ValueError("Overture returned no polygonal land-use features for the AOI")

    with connect() as conn:
        version = next_layer_version(conn, "land_use")
        conn.execute(
            text(
                "DELETE FROM land_use_areas "
                "WHERE designation = :designation AND source = :source"
            ),
            {"designation": DESIGNATION, "source": SOURCE_NAME},
        )
        conn.execute(
            text(
                """
                WITH candidate AS (
                  SELECT ST_MakeValid(
                           ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326)
                         ) AS geom
                ), clipped AS (
                  SELECT ST_Multi(ST_CollectionExtract(
                           ST_Intersection(c.geom, b.geom), 3
                         )) AS geom
                  FROM candidate c
                  CROSS JOIN territory_boundaries b
                  WHERE b.name = 'Federal Capital Territory'
                )
                INSERT INTO land_use_areas (
                  geom, source_id, category, source_class, source_subtype, name,
                  designation, source, source_url, layer_version
                )
                SELECT geom, :source_id, :category, :source_class, :source_subtype, :name,
                       :designation, :source, :source_url, :layer_version
                FROM clipped
                WHERE geom IS NOT NULL AND NOT ST_IsEmpty(geom)
                """
            ),
            [
                {
                    **record.__dict__,
                    "designation": DESIGNATION,
                    "source": SOURCE_NAME,
                    "source_url": SOURCE_URL,
                    "layer_version": version,
                }
                for record in records
            ],
        )
        qa = conn.execute(
            text(
                """
                WITH boundary AS (
                  SELECT geom FROM territory_boundaries
                  WHERE name = 'Federal Capital Territory'
                ), mapped AS (
                  SELECT COUNT(*) AS features,
                         ST_UnaryUnion(ST_Collect(l.geom)) AS geom
                  FROM land_use_areas l
                  WHERE l.designation = :designation AND l.source = :source
                )
                SELECT m.features,
                       ROUND((ST_Area(m.geom::geography) / 1000000.0)::numeric, 1)
                         AS mapped_sqkm,
                       ROUND((100 * ST_Area(m.geom::geography) /
                         NULLIF(ST_Area(b.geom::geography), 0))::numeric, 1)
                         AS territory_coverage_pct,
                       COALESCE((
                         SELECT MAX(ST_Area(ST_Difference(l.geom, b.geom)::geography))
                         FROM land_use_areas l
                         WHERE l.designation = :designation AND l.source = :source
                       ), 0) < 1 AS clipped_to_fct
                FROM boundary b CROSS JOIN mapped m
                """
            ),
            {"designation": DESIGNATION, "source": SOURCE_NAME},
        ).mappings().one()
        published_counts = {
            str(row["category"]): int(row["count"])
            for row in conn.execute(
                text(
                    """
                    SELECT category, COUNT(*) AS count
                    FROM land_use_areas
                    WHERE designation = :designation AND source = :source
                    GROUP BY category
                    """
                ),
                {"designation": DESIGNATION, "source": SOURCE_NAME},
            ).mappings()
        }
        published, invalidated = bump_layer(
            conn,
            "land_use",
            source=f"Overture Maps {release} / OpenStreetMap",
            notes=(
                f"{qa['features']} clipped open-reference polygons; "
                f"{qa['territory_coverage_pct']}% FCT coverage; not statutory AGIS zoning"
            ),
        )
        if published != version:
            raise RuntimeError("land-use layer version changed during publication")

    summary = {
        "status": "published",
        "version": version,
        "release": release,
        "features": qa["features"],
        "categories": dict(sorted(published_counts.items())),
        "designation": DESIGNATION,
        "mapped_sqkm": float(qa["mapped_sqkm"]),
        "territory_coverage_pct": float(qa["territory_coverage_pct"]),
        "clipped_to_fct": qa["clipped_to_fct"],
        "scores_invalidated": invalidated,
    }
    log.info("refresh_land_use complete: %s", summary)
    return summary

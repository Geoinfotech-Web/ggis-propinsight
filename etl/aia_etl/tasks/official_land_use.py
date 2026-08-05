"""Import licensed AGIS/FCTA planning vectors with authoritative precedence."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.db import connect
from aia_etl.layers import bump_layer, next_layer_version
from aia_etl.sources.official_land_use import (
    load_feature_collection,
    records_from_feature_collection,
)
from aia_etl.tasks.boundaries import refresh_fct_boundary

log = logging.getLogger(__name__)
DESIGNATION = "official_masterplan"


@app.task(name="aia_etl.tasks.official_land_use.import_official_land_use")
def import_official_land_use(
    path: str,
    dataset_name: str,
    category_field: str,
    name_field: str | None = None,
    effective_date: str | None = None,
    source_url: str | None = None,
    layer: str | None = None,
) -> dict[str, Any]:
    """Load a licensed official plan; publication permission remains a data prerequisite."""
    refresh_fct_boundary.run()
    payload = load_feature_collection(path, layer=layer)
    records = records_from_feature_collection(
        payload,
        dataset_name=dataset_name,
        category_field=category_field,
        name_field=name_field,
    )
    effective = date.fromisoformat(effective_date) if effective_date else None
    source_name = f"AGIS/FCTA — {dataset_name}"[:160]

    with connect() as conn:
        version = next_layer_version(conn, "land_use")
        conn.execute(
            text(
                "DELETE FROM land_use_areas "
                "WHERE designation = :designation AND source = :source"
            ),
            {"designation": DESIGNATION, "source": source_name},
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
                  geom, source_id, category, source_class, name, designation,
                  source, source_url, effective_date, layer_version
                )
                SELECT geom, :source_id, :category, :source_class, :name, :designation,
                       :source, :source_url, :effective_date, :layer_version
                FROM clipped
                WHERE geom IS NOT NULL AND NOT ST_IsEmpty(geom)
                """
            ),
            [
                {
                    **record.__dict__,
                    "designation": DESIGNATION,
                    "source": source_name,
                    "source_url": source_url,
                    "effective_date": effective,
                    "layer_version": version,
                }
                for record in records
            ],
        )
        inserted = conn.execute(
            text(
                "SELECT COUNT(*) FROM land_use_areas "
                "WHERE designation = :designation AND source = :source"
            ),
            {"designation": DESIGNATION, "source": source_name},
        ).scalar_one()
        if not inserted:
            raise ValueError("official planning features did not intersect the FCT boundary")
        published, invalidated = bump_layer(
            conn,
            "land_use",
            source=source_name,
            notes=f"{inserted} official planning polygons from {dataset_name}",
        )
        if published != version:
            raise RuntimeError("land-use layer version changed during official publication")

    summary = {
        "status": "published",
        "version": version,
        "dataset": dataset_name,
        "designation": DESIGNATION,
        "features": inserted,
        "categories": dict(sorted(Counter(record.category for record in records).items())),
        "effective_date": effective_date,
        "scores_invalidated": invalidated,
    }
    log.info("import_official_land_use complete: %s", summary)
    return summary

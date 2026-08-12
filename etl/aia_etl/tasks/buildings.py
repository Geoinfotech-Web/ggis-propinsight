"""Publish an FCT analytical building layer from Overture Maps."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer, next_layer_version
from aia_etl.sources.base import FCT_BBOX
from aia_etl.sources.overture_buildings import (
    SOURCE_NAME,
    SOURCE_URL,
    iter_overture_building_batches,
)
from aia_etl.tasks.boundaries import refresh_fct_boundary

log = logging.getLogger(__name__)
settings = get_settings()

INSERT_SQL = text(
    """
    WITH records AS (
      SELECT * FROM jsonb_to_recordset(CAST(:records AS jsonb)) AS r(
        source_id text, parent_source_id text, feature_type text,
        building_class text, height_m double precision, num_floors integer,
        min_height_m double precision, display_height_m double precision,
        height_basis text, source_datasets jsonb, release text,
        layer_version text, geometry jsonb
      )
    ), candidate AS (
      SELECT r.*, ST_SetSRID(ST_GeomFromGeoJSON(r.geometry::text), 4326) AS geom
      FROM records r
    ), fct_buildings AS (
      SELECT c.*, ST_Multi(ST_CollectionExtract(c.geom, 3)) AS building_geom
      FROM candidate c CROSS JOIN territory_boundaries b
      WHERE b.name = 'Federal Capital Territory'
        AND b.geom && c.geom
        AND ST_Covers(b.geom, ST_PointOnSurface(c.geom))
    )
    INSERT INTO building_footprints (
      source_id, parent_source_id, feature_type, building_class, height_m,
      num_floors, min_height_m, display_height_m, height_basis,
      source_datasets, release, layer_version, geom
    )
    SELECT source_id, parent_source_id, feature_type, building_class, height_m,
           num_floors, min_height_m, display_height_m, height_basis,
           source_datasets, release, layer_version, building_geom
    FROM fct_buildings
    WHERE building_geom IS NOT NULL AND NOT ST_IsEmpty(building_geom)
    """
)


@app.task(name="aia_etl.tasks.buildings.refresh_buildings")
def refresh_buildings(bbox: list[float] | None = None) -> dict[str, Any]:
    refresh_fct_boundary.run()
    aoi = tuple(bbox) if bbox else FCT_BBOX
    release, batches = iter_overture_building_batches(  # type: ignore[arg-type]
        aoi, settings.overture_release
    )

    with connect() as conn:
        version = next_layer_version(conn, "buildings_3d")
        conn.execute(text("DELETE FROM building_footprints"))
        source_features = 0
        for records in batches:
            source_features += len(records)
            payload = [
                {
                    **record.__dict__,
                    "geometry": json.loads(record.geometry),
                    "source_datasets": list(record.source_datasets),
                    "release": release,
                    "layer_version": version,
                }
                for record in records
            ]
            conn.execute(INSERT_SQL, {"records": json.dumps(payload)})
        if source_features == 0:
            raise ValueError("Overture returned no building footprints for the AOI")
        counts = dict(
            conn.execute(
                text("SELECT height_basis, COUNT(*) FROM building_footprints GROUP BY height_basis")
            ).all()
        )
        published, invalidated = bump_layer(
            conn,
            "buildings_3d",
            source=f"{SOURCE_NAME} {release}",
            notes=(
                f"{sum(int(value) for value in counts.values())} FCT analytical building "
                f"features from {source_features} source candidates; {SOURCE_URL}"
            ),
        )
        if published != version:
            raise RuntimeError("buildings layer version changed during publication")
    return {
        "status": "published",
        "version": version,
        "release": release,
        "features": sum(int(value) for value in counts.values()),
        "height_basis_counts": counts,
        "scores_invalidated": invalidated,
    }

"""Publish a dissolved operational FCT boundary with explicit provenance."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.sources.grid3_boundaries import (
    SOURCE_ITEM_URL,
    SOURCE_NAME,
    BoundaryPayload,
    fetch_fct_wards,
)

log = logging.getLogger(__name__)
settings = get_settings()


def publish_fct_boundary(conn: Connection, payload: BoundaryPayload) -> dict[str, Any]:
    """Publish ward polygons and their dissolved FCT boundary in one transaction."""
    ward_rows = conn.execute(
        text(
            """
            INSERT INTO wards (
              source_id, name, area_council, state, source, source_url,
              source_version, geom, updated_at
            )
            SELECT
              value->>'source_id', value->>'name', value->>'area_council',
              value->>'state', :source, :source_url, :source_version,
              ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SetSRID(
                ST_GeomFromGeoJSON((value->'geometry')::text), 4326
              )), 3)), NOW()
            FROM jsonb_array_elements(CAST(:wards AS jsonb)) AS value
            WHERE value->'geometry' IS NOT NULL
            ON CONFLICT (source_id) DO UPDATE
              SET name = EXCLUDED.name,
                  area_council = EXCLUDED.area_council,
                  state = EXCLUDED.state,
                  source = EXCLUDED.source,
                  source_url = EXCLUDED.source_url,
                  source_version = EXCLUDED.source_version,
                  geom = EXCLUDED.geom,
                  updated_at = EXCLUDED.updated_at
            RETURNING id
            """
        ),
        {
            "wards": json.dumps(payload.wards),
            "source": SOURCE_NAME,
            "source_url": SOURCE_ITEM_URL,
            "source_version": payload.source_version,
        },
    ).rowcount
    row = conn.execute(
        text(
            """
            WITH parts AS (
              SELECT ST_MakeValid(
                ST_SetSRID(ST_GeomFromGeoJSON(value::text), 4326)
              ) AS geom
              FROM jsonb_array_elements(CAST(:geometries AS jsonb)) AS value
            ), dissolved AS (
              SELECT ST_Multi(
                ST_CollectionExtract(ST_UnaryUnion(ST_Collect(geom)), 3)
              ) AS geom
              FROM parts
            )
            INSERT INTO territory_boundaries (
              name, source, source_url, source_version, geom, updated_at
            )
            SELECT 'Federal Capital Territory', :source, :source_url,
                   :source_version, geom, NOW()
            FROM dissolved
            WHERE geom IS NOT NULL AND NOT ST_IsEmpty(geom)
            ON CONFLICT (name) DO UPDATE
              SET source = EXCLUDED.source,
                  source_url = EXCLUDED.source_url,
                  source_version = EXCLUDED.source_version,
                  geom = EXCLUDED.geom,
                  updated_at = EXCLUDED.updated_at
            RETURNING ROUND((ST_Area(geom::geography) / 1000000.0)::numeric, 1)
                      AS area_sqkm,
                      ST_XMin(geom) AS min_lon, ST_YMin(geom) AS min_lat,
                      ST_XMax(geom) AS max_lon, ST_YMax(geom) AS max_lat
            """
        ),
        {
            "geometries": json.dumps(payload.geometries),
            "source": SOURCE_NAME,
            "source_url": SOURCE_ITEM_URL,
            "source_version": payload.source_version,
        },
    ).mappings().one()
    conn.execute(
        text(
            """
            INSERT INTO layer_registry (layer, version, source, notes, updated_at)
            VALUES (
              'administrative_boundaries', :version, :source,
              'GRID3 FCT operational wards for local context', NOW()
            )
            ON CONFLICT (layer) DO UPDATE
              SET version = EXCLUDED.version,
                  source = EXCLUDED.source,
                  notes = EXCLUDED.notes,
                  updated_at = EXCLUDED.updated_at
            """
        ),
        {"version": payload.source_version, "source": SOURCE_NAME},
    )
    return {"published_wards": ward_rows, **dict(row)}


@app.task(name="aia_etl.tasks.boundaries.refresh_fct_boundary")
def refresh_fct_boundary() -> dict[str, Any]:
    payload = fetch_fct_wards(settings.grid3_wards_url)
    with connect() as conn:
        stats = publish_fct_boundary(conn, payload)
    summary = {
        "status": "published",
        "source": SOURCE_NAME,
        "source_version": payload.source_version,
        "wards": payload.ward_count,
        **stats,
    }
    log.info("refresh_fct_boundary complete: %s", summary)
    return summary

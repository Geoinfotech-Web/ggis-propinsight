"""Publish wall-to-wall observed cover separately from statutory land use."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer, next_layer_version
from aia_etl.sources.canopy import canopy_geometries
from aia_etl.sources.worldcover import (
    DYNAMIC_WORLD_CLASSES,
    WORLD_COVER_CLASSES,
    export_worldcover,
    write_clipped_cog,
)
from aia_etl.sources.worldcover import (
    SOURCE_NAME as WORLDCOVER_NAME,
)
from aia_etl.sources.worldcover import (
    SOURCE_URL as WORLDCOVER_URL,
)
from aia_etl.tasks.boundaries import refresh_fct_boundary

log = logging.getLogger(__name__)
settings = get_settings()

DYNAMIC_WORLD_NAME = "Google Dynamic World V1"
DYNAMIC_WORLD_URL = (
    "https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1"
)

CANOPY_INSERT_SQL = text(
    """
    WITH source AS (
      SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326) AS geom
    ), metric AS (
      SELECT ST_Transform(ST_CollectionExtract(geom, 3), 3857) AS geom FROM source
    ), prepared AS (
      SELECT ST_Multi(ST_Transform(ST_CollectionExtract(ST_MakeValid(
               geom
             ), 3), 4326)) AS geom,
             ST_Area(geom) / 10000.0 AS area_ha
      FROM metric WHERE ST_Area(geom) >= 2500.0
    )
    INSERT INTO vegetation_canopy_areas (
      source, source_url, period_start, period_end, resolution_m,
      area_ha, layer_version, geom
    )
    SELECT :source, :source_url, :period_start, :period_end, :resolution_m,
           area_ha, :layer_version, geom
    FROM prepared WHERE geom IS NOT NULL AND NOT ST_IsEmpty(geom)
    """
)


def _publish_canopy(
    conn: Any,
    *,
    geometries: Iterable[dict[str, Any]],
    source_name: str,
    source_url: str,
    period_start: date,
    period_end: date,
    resolution_m: int,
) -> tuple[int, int, int]:
    """Atomically replace the published canopy layer and return version/count/invalidations."""
    vegetation_version = next_layer_version(conn, "vegetation_3d")
    conn.execute(text("DELETE FROM vegetation_canopy_areas"))
    canopy_payload: list[dict[str, Any]] = []
    for geometry in geometries:
        canopy_payload.append({
            "geometry": json.dumps(geometry),
            "source": source_name,
            "source_url": source_url,
            "period_start": period_start,
            "period_end": period_end,
            "resolution_m": resolution_m,
            "layer_version": vegetation_version,
        })
        if len(canopy_payload) == 500:
            conn.execute(CANOPY_INSERT_SQL, canopy_payload)
            canopy_payload.clear()
    if canopy_payload:
        conn.execute(CANOPY_INSERT_SQL, canopy_payload)
    canopy_count = int(
        conn.execute(text("SELECT COUNT(*) FROM vegetation_canopy_areas")).scalar_one()
    )
    published, invalidated = bump_layer(
        conn,
        "vegetation_3d",
        source=source_name,
        notes=(
            f"{canopy_count} connected observed tree-cover patches >= 0.25 ha; "
            "not an individual tree inventory"
        ),
    )
    if published != vegetation_version:
        raise RuntimeError("vegetation layer version changed during publication")
    return published, canopy_count, invalidated


def _boundary_context() -> tuple[tuple[float, float, float, float], list[dict[str, Any]]]:
    with connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom),
                       ST_AsGeoJSON(geom)
                FROM territory_boundaries
                WHERE name = 'Federal Capital Territory'
                """
            )
        ).one()
    return (float(row[0]), float(row[1]), float(row[2]), float(row[3])), [json.loads(row[4])]


def _dynamic_world(
    bounds: tuple[float, float, float, float],
    geometries: list[dict[str, Any]],
    out_path: Path,
    start: date,
    end: date,
) -> Path:
    from aia_etl.gee import export_dynamic_world_mode

    raw_path = out_path.with_name(f"{out_path.stem}.raw.tif")
    export_dynamic_world_mode(
        bounds,
        raw_path,
        start.isoformat(),
        end.isoformat(),
        scale=settings.land_cover_scale_m,
    )
    try:
        return write_clipped_cog([raw_path], bounds, geometries, out_path)
    finally:
        raw_path.unlink(missing_ok=True)


@app.task(name="aia_etl.tasks.land_cover.refresh_land_cover")
def refresh_land_cover(source: str | None = None) -> dict[str, Any]:
    """Publish Dynamic World when available, otherwise ESA WorldCover."""
    refresh_fct_boundary.run()
    bounds, geometries = _boundary_context()
    requested = (source or settings.land_cover_source).lower()
    if requested not in {"auto", "dynamic_world", "esa_worldcover"}:
        raise ValueError("land-cover source must be auto, dynamic_world, or esa_worldcover")

    period_end = date.today().replace(day=1)
    period_start = period_end - timedelta(days=365)
    with connect() as conn:
        version = next_layer_version(conn, "land_cover")
    out_path = Path(settings.data_dir) / "land_cover" / f"land_cover_{version}.tif"

    selected = requested
    if requested in {"auto", "dynamic_world"}:
        try:
            _dynamic_world(bounds, geometries, out_path, period_start, period_end)
            selected = "dynamic_world"
        except Exception:  # noqa: BLE001 - auto must survive external IAM/source outages
            if requested == "dynamic_world":
                raise
            log.warning("Dynamic World unavailable; falling back to ESA WorldCover", exc_info=True)
            selected = "esa_worldcover"

    if selected == "esa_worldcover":
        export_worldcover(bounds, geometries, out_path)
        source_name = WORLDCOVER_NAME
        source_url = WORLDCOVER_URL
        classes = WORLD_COVER_CLASSES
        period_start = date(2021, 1, 1)
        period_end = date(2021, 12, 31)
        resolution_m = 10
    else:
        source_name = DYNAMIC_WORLD_NAME
        source_url = DYNAMIC_WORLD_URL
        classes = DYNAMIC_WORLD_CLASSES
        resolution_m = settings.land_cover_scale_m

    canopy = canopy_geometries(out_path, classes, resolution_m)

    with connect() as conn:
        conn.execute(text("DELETE FROM land_cover_rasters"))
        conn.execute(
            text(
                """
                INSERT INTO land_cover_rasters (
                  source, source_url, raster_path, period_start, period_end,
                  resolution_m, classes, layer_version
                ) VALUES (
                  :source, :source_url, :raster_path, :period_start, :period_end,
                  :resolution_m, CAST(:classes AS jsonb), :layer_version
                )
                """
            ),
            {
                "source": source_name,
                "source_url": source_url,
                "raster_path": str(out_path),
                "period_start": period_start,
                "period_end": period_end,
                "resolution_m": resolution_m,
                "classes": json.dumps(classes),
                "layer_version": version,
            },
        )
        vegetation_version, canopy_count, vegetation_invalidated = _publish_canopy(
            conn,
            geometries=canopy,
            source_name=source_name,
            source_url=source_url,
            period_start=period_start,
            period_end=period_end,
            resolution_m=resolution_m,
        )
        published, invalidated = bump_layer(
            conn,
            "land_cover",
            source=source_name,
            notes="Wall-to-wall observed cover clipped to GRID3 FCT; not statutory zoning",
        )
        if published != version:
            raise RuntimeError("land-cover layer version changed during publication")

    summary = {
        "status": "published",
        "version": version,
        "source": source_name,
        "requested_source": requested,
        "raster_path": str(out_path),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "resolution_m": resolution_m,
        "scores_invalidated": invalidated,
        "canopy_features": canopy_count,
        "vegetation_version": vegetation_version,
        "vegetation_scores_invalidated": vegetation_invalidated,
    }
    log.info("refresh_land_cover complete: %s", summary)
    return summary


@app.task(name="aia_etl.tasks.land_cover.refresh_vegetation_canopy")
def refresh_vegetation_canopy() -> dict[str, Any]:
    """Rebuild canopy zones from the currently published observed land-cover COG."""
    with connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT source, source_url, raster_path, period_start, period_end,
                       resolution_m, classes
                FROM land_cover_rasters
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        ).mappings().one_or_none()
    if row is None:
        raise RuntimeError("No published land-cover raster is available for canopy generation")

    raster_path = Path(str(row["raster_path"]))
    if not raster_path.exists():
        raise RuntimeError(f"Published land-cover raster is missing: {raster_path}")
    classes = row["classes"]
    if isinstance(classes, str):
        classes = json.loads(classes)
    geometries = canopy_geometries(raster_path, classes, int(row["resolution_m"]))
    with connect() as conn:
        version, feature_count, invalidated = _publish_canopy(
            conn,
            geometries=geometries,
            source_name=str(row["source"]),
            source_url=str(row["source_url"]),
            period_start=row["period_start"],
            period_end=row["period_end"],
            resolution_m=int(row["resolution_m"]),
        )
    summary = {
        "status": "published",
        "version": version,
        "source": str(row["source"]),
        "raster_path": str(raster_path),
        "feature_count": feature_count,
        "scores_invalidated": invalidated,
    }
    log.info("refresh_vegetation_canopy complete: %s", summary)
    return summary

"""Publish wall-to-wall observed cover separately from statutory land use."""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer, next_layer_version
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
    }
    log.info("refresh_land_cover complete: %s", summary)
    return summary

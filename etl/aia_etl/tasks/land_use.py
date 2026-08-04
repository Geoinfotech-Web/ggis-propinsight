"""Publish open land-use context separately from statutory planning overlays."""
from __future__ import annotations

import logging
from collections import Counter
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

log = logging.getLogger(__name__)
settings = get_settings()


@app.task(name="aia_etl.tasks.land_use.refresh_land_use")
def refresh_land_use(bbox: list[float] | None = None) -> dict[str, Any]:
    """Refresh FCT open land use; never present it as official AGIS zoning."""
    aoi = tuple(bbox) if bbox else FCT_BBOX
    records, release = fetch_overture_land_use(aoi, settings.overture_release)  # type: ignore[arg-type]
    if not records:
        raise ValueError("Overture returned no polygonal land-use features for the AOI")

    counts = Counter(record.category for record in records)
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
                INSERT INTO land_use_areas (
                  geom, source_id, category, source_class, source_subtype, name,
                  designation, source, source_url, layer_version
                ) VALUES (
                  ST_SetSRID(ST_Multi(ST_GeomFromGeoJSON(:geometry)), 4326),
                  :source_id, :category, :source_class, :source_subtype, :name,
                  :designation, :source, :source_url, :layer_version
                )
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
        published, invalidated = bump_layer(
            conn,
            "land_use",
            source=f"Overture Maps {release} / OpenStreetMap",
            notes=(
                f"{len(records)} open reference polygons; not statutory AGIS zoning"
            ),
        )
        if published != version:
            raise RuntimeError("land-use layer version changed during publication")

    summary = {
        "status": "published",
        "version": version,
        "release": release,
        "features": len(records),
        "categories": dict(sorted(counts.items())),
        "designation": DESIGNATION,
        "scores_invalidated": invalidated,
    }
    log.info("refresh_land_use complete: %s", summary)
    return summary

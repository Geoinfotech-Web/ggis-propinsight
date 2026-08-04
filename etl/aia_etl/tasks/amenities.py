"""Multi-source amenity (POI) refresh (Overview §6.3).

Pulls POIs from the configured open sources (Overpass/OSM, Overture Maps, …),
normalises and de-duplicates them, publishes each source's rows independently,
and bumps the `poi` layer once — which invalidates dependent cached scorecards.

Not limited to OSM: adding a provider is a new adapter in `aia_etl.sources`, not
a schema or API change.
"""
from __future__ import annotations

import logging
from typing import Any

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer
from aia_etl.sources.base import FCT_BBOX, PoiRecord, dedup_records, replace_source_pois

log = logging.getLogger(__name__)
settings = get_settings()

BBox = tuple[float, float, float, float]


def _fetch(source: str, bbox: BBox) -> list[PoiRecord]:
    if source == "overpass":
        from aia_etl.sources.overpass import fetch_overpass

        return fetch_overpass(bbox)
    if source == "overture":
        from aia_etl.sources.overture import fetch_overture

        return fetch_overture(bbox)
    if source == "grid3":
        from aia_etl.sources.grid3 import fetch_grid3

        return fetch_grid3(bbox)
    raise ValueError(f"unknown POI source {source!r}")


@app.task(name="aia_etl.tasks.amenities.refresh_amenities")
def refresh_amenities(
    sources: list[str] | None = None, bbox: list[float] | None = None
) -> dict[str, Any]:
    """Refresh POIs from the given (or configured) sources for the AOI."""
    aoi: BBox = tuple(bbox) if bbox else FCT_BBOX  # type: ignore[assignment]
    src_list = sources or settings.poi_sources_list

    # Bump the layer first so every source publishes under one new version and
    # dependent scorecards are swept once.
    with connect() as conn:
        version, invalidated = bump_layer(conn, "poi", source="+".join(src_list))

    per_source: dict[str, int] = {}
    for source in src_list:
        raw = _fetch(source, aoi)
        clean = dedup_records([r for r in raw if r.valid(aoi)])
        with connect() as conn:
            per_source[source] = replace_source_pois(conn, source, clean, version)

    summary = {
        "aoi": list(aoi),
        "poi_version": version,
        "sources": per_source,
        "total_pois": sum(per_source.values()),
        "scores_invalidated": invalidated,
    }
    log.info("refresh_amenities complete: %s", summary)
    return summary

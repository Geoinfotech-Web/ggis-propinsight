"""GRID3 Nigeria facilities (non-OSM) via ArcGIS FeatureServers.

GRID3 (geo-referenced infrastructure & demographic data) publishes Nigerian
health and education facility layers as ArcGIS FeatureServers. Configure the
layer URLs in `.env` (GRID3_HEALTH_URL / GRID3_EDUCATION_URL); each maps to a
fixed AIA category. Non-OSM, no API key. License: CC-BY-4.0 (attribute GRID3).
"""
from __future__ import annotations

import logging

from aia_etl.config import get_settings
from aia_etl.sources.arcgis import fetch_arcgis_layer
from aia_etl.sources.base import PoiRecord

log = logging.getLogger(__name__)


def configured_layers() -> list[tuple[str, str]]:
    """(FeatureServer layer URL, AIA category) pairs that are configured."""
    s = get_settings()
    layers: list[tuple[str, str]] = []
    if s.grid3_health_url:
        layers.append((s.grid3_health_url, "hospital"))
    if s.grid3_education_url:
        layers.append((s.grid3_education_url, "school"))
    return layers


def fetch_grid3(bbox: tuple[float, float, float, float]) -> list[PoiRecord]:
    layers = configured_layers()
    if not layers:
        log.warning(
            "GRID3 source enabled but no layer URLs configured "
            "(set GRID3_HEALTH_URL / GRID3_EDUCATION_URL in .env)."
        )
        return []
    records: list[PoiRecord] = []
    for url, category in layers:
        try:
            records.extend(fetch_arcgis_layer(url, category, bbox))
        except Exception as exc:  # noqa: BLE001 — one layer failing shouldn't drop others
            log.error("GRID3 layer %s failed: %s", url, exc)
    return records

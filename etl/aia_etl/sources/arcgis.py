"""Generic ArcGIS FeatureServer POI adapter (non-OSM).

Many open registries — GRID3, state GIS agencies, health/education ministries —
publish facilities as ArcGIS FeatureServer layers that answer paginated GeoJSON
queries with a bbox filter and no API key. This adapter turns one such layer
(mapped to a fixed AIA category) into PoiRecords.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from aia_etl.sources.base import PoiRecord

log = logging.getLogger(__name__)

PAGE_SIZE = 1000
# Common attribute keys registries use for a facility's name (first hit wins).
_NAME_FIELDS = (
    "name", "Name", "NAME", "facility_name", "facilityname", "fac_name",
    "prmry_name", "primary_name", "school_name", "hf_name", "wardname",
)


def build_params(
    bbox: tuple[float, float, float, float], offset: int, page: int = PAGE_SIZE
) -> dict[str, Any]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "where": "1=1",
        "geometry": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": page,
    }


def _name_of(props: dict[str, Any], name_field: str | None) -> str | None:
    if name_field and props.get(name_field):
        return str(props[name_field])
    for key in _NAME_FIELDS:
        if props.get(key):
            return str(props[key])
    return None


def map_feature(
    feature: dict[str, Any], category: str, name_field: str | None = None
) -> PoiRecord | None:
    geom = feature.get("geometry") or {}
    if geom.get("type") != "Point":
        return None
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        return None
    lon, lat = coords[0], coords[1]
    return PoiRecord(
        lon=float(lon),
        lat=float(lat),
        category=category,
        name=_name_of(feature.get("properties") or {}, name_field),
        source="grid3",
    )


def fetch_arcgis_layer(
    url: str,
    category: str,
    bbox: tuple[float, float, float, float],
    *,
    name_field: str | None = None,
    timeout_s: float = 60.0,
    max_pages: int = 50,
) -> list[PoiRecord]:
    """Query one FeatureServer layer's `/query` endpoint, paginated, within bbox."""
    query_url = url.rstrip("/")
    if not query_url.endswith("/query"):
        query_url += "/query"

    records: list[PoiRecord] = []
    with httpx.Client(timeout=timeout_s) as client:
        for page_i in range(max_pages):
            params = build_params(bbox, offset=page_i * PAGE_SIZE)
            resp = client.get(query_url, params=params)
            resp.raise_for_status()
            features = resp.json().get("features", [])
            if not features:
                break
            for feat in features:
                rec = map_feature(feat, category, name_field)
                if rec is not None:
                    records.append(rec)
            if len(features) < PAGE_SIZE:
                break
    log.info("ArcGIS %s -> %d %s POIs", query_url, len(records), category)
    return records

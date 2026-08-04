"""OpenStreetMap POIs via the Overpass API.

Comprehensive AOI coverage without a Geofabrik bulk download — a live query for
the amenity/shop/etc. tags AIA maps to its categories. Good for filling all of
the FCT immediately; the monthly Geofabrik path (tasks/osm.py) remains for bulk
loads. License: ODbL (attribution + share-alike on derived data).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from aia_etl.poi_categories import categorize
from aia_etl.sources.base import PoiRecord

log = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Overpass rejects requests without a descriptive User-Agent (406).
_HEADERS = {
    "User-Agent": "PropInsight/0.1 (Geoinfotech GGIS; github.com/Geoinfotech-Web/ggis-propinsight)",
    "Accept": "application/json",
}

# OSM key/value selectors that map to an AIA category (kept aligned with
# poi_categories._TAG_MAP so categorize() resolves them).
_SELECTORS: tuple[tuple[str, str], ...] = (
    ("amenity", "school"), ("amenity", "kindergarten"), ("amenity", "college"),
    ("amenity", "university"), ("amenity", "hospital"), ("amenity", "clinic"),
    ("amenity", "doctors"), ("amenity", "pharmacy"), ("amenity", "marketplace"),
    ("amenity", "bank"), ("amenity", "atm"), ("amenity", "fuel"),
    ("amenity", "place_of_worship"), ("amenity", "drinking_water"),
    ("shop", "supermarket"), ("shop", "mall"),
    ("man_made", "water_well"), ("man_made", "water_works"), ("man_made", "borehole"),
    ("power", "substation"), ("power", "plant"),
)


def build_query(bbox: tuple[float, float, float, float], timeout: int = 120) -> str:
    """Overpass QL for nodes+ways of the selectors within bbox (S,W,N,E order)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    area = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    parts = []
    for key, value in _SELECTORS:
        parts.append(f'  node["{key}"="{value}"]({area});')
        parts.append(f'  way["{key}"="{value}"]({area});')
    body = "\n".join(parts)
    return f"[out:json][timeout:{timeout}];\n(\n{body}\n);\nout center tags;"


def map_element(element: dict[str, Any]) -> PoiRecord | None:
    """Map one Overpass element to a PoiRecord (None if not categorisable)."""
    tags = element.get("tags") or {}
    category = categorize(tags)
    if category is None:
        return None
    if element.get("type") == "node":
        lon, lat = element.get("lon"), element.get("lat")
    else:  # way/relation → use the computed center
        center = element.get("center") or {}
        lon, lat = center.get("lon"), center.get("lat")
    if lon is None or lat is None:
        return None
    return PoiRecord(
        lon=float(lon),
        lat=float(lat),
        category=category,
        name=tags.get("name"),
        source="overpass",
    )


def fetch_overpass(
    bbox: tuple[float, float, float, float], timeout_s: float = 180.0
) -> list[PoiRecord]:
    query = build_query(bbox)
    log.info("Overpass query for bbox %s", bbox)
    with httpx.Client(timeout=timeout_s, headers=_HEADERS) as client:
        resp = client.post(OVERPASS_URL, data={"data": query})
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    records = [rec for el in elements if (rec := map_element(el)) is not None]
    log.info("Overpass returned %d elements -> %d POIs", len(elements), len(records))
    return records

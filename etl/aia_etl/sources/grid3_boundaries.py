"""GRID3 operational boundaries used to clip open reference layers to FCT."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

SOURCE_NAME = "GRID3 NGA Operational Wards"
SOURCE_ITEM_URL = "https://www.arcgis.com/home/item.html?id=45cd2ef592094d12aca43113a90a6054"


@dataclass(frozen=True)
class BoundaryPayload:
    wards: list[dict[str, Any]]
    source_version: str

    @property
    def geometries(self) -> list[dict[str, Any]]:
        return [ward["geometry"] for ward in self.wards]

    @property
    def ward_count(self) -> int:
        return len(self.wards)


def fetch_fct_wards(layer_url: str) -> BoundaryPayload:
    """Fetch the current FCT wards as GeoJSON; PostGIS dissolves them on publish."""
    response = requests.get(
        f"{layer_url.rstrip('/')}/query",
        params={
            "where": "state='FCT, Abuja'",
            "outFields": "OBJECTID,state,lga,ward,date",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    features = payload.get("features") or []
    wards = [
        {
            "source_id": str(feature.get("properties", {}).get("OBJECTID") or ""),
            "name": str(feature.get("properties", {}).get("ward") or "Unknown ward"),
            "area_council": str(feature.get("properties", {}).get("lga") or "Unknown"),
            "state": str(feature.get("properties", {}).get("state") or "FCT, Abuja"),
            "geometry": feature["geometry"],
        }
        for feature in features
        if feature.get("geometry", {}).get("type") in {"Polygon", "MultiPolygon"}
    ]
    if not wards:
        raise ValueError("GRID3 returned no polygonal FCT wards")
    versions = [
        str(feature.get("properties", {}).get("date") or "") for feature in features
    ]
    return BoundaryPayload(
        wards=wards,
        source_version=max((version for version in versions if version), default="unknown"),
    )

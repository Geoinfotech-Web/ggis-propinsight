"""Normalize official planning vectors into the product land-use taxonomy."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OfficialLandUseRecord:
    source_id: str
    geometry: str
    category: str
    source_class: str
    name: str | None


def normalise_official_category(value: object) -> str:
    raw = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    if "residen" in raw or "housing" in raw:
        return "residential"
    if "industr" in raw or "manufactur" in raw or "warehouse" in raw:
        return "industrial"
    if any(term in raw for term in ("commercial", "retail", "business", "market")):
        return "commercial"
    if any(
        term in raw
        for term in ("institution", "education", "school", "health", "hospital", "religious")
    ):
        return "institutional"
    if any(term in raw for term in ("reserve", "protected", "conservation", "green belt")):
        return "protected_reserve"
    if any(term in raw for term in ("park", "recreation", "open space", "green area")):
        return "recreation_open_space"
    if any(term in raw for term in ("agric", "farm", "horticultur")):
        return "agricultural"
    if any(term in raw for term in ("military", "defence", "restricted", "security")):
        return "military_restricted"
    if any(term in raw for term in ("transport", "road", "rail", "airport", "terminal")):
        return "transportation"
    if any(term in raw for term in ("construction", "future development", "development")):
        return "construction_development"
    if any(term in raw for term in ("quarry", "mining", "extract")):
        return "extractive"
    if "landfill" in raw or "waste" in raw:
        return "landfill"
    if "cemet" in raw or "burial" in raw:
        return "cemetery"
    return "other"


def load_feature_collection(path: str, layer: str | None = None) -> dict[str, Any]:
    """Use GDAL to normalize GeoJSON, Shapefile, or GeoPackage to EPSG:4326."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    command = [
        "ogr2ogr",
        "-f",
        "GeoJSON",
        "/vsistdout/",
        str(source),
        "-t_srs",
        "EPSG:4326",
    ]
    if layer:
        command.append(layer)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    if payload.get("type") != "FeatureCollection":
        raise ValueError("official planning input did not normalize to a FeatureCollection")
    return payload


def records_from_feature_collection(
    payload: dict[str, Any],
    *,
    dataset_name: str,
    category_field: str,
    name_field: str | None = None,
) -> list[OfficialLandUseRecord]:
    records: list[OfficialLandUseRecord] = []
    for index, feature in enumerate(payload.get("features") or []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        properties = feature.get("properties") or {}
        source_class = str(properties.get(category_field) or "").strip()
        if not source_class:
            continue
        raw_id = feature.get("id") or properties.get("id") or properties.get("OBJECTID") or index
        digest = hashlib.sha1(
            f"{dataset_name}:{raw_id}".encode(), usedforsecurity=False
        ).hexdigest()[:32]
        name = str(properties.get(name_field) or "").strip() if name_field else ""
        records.append(
            OfficialLandUseRecord(
                source_id=f"official:{digest}",
                geometry=json.dumps(geometry),
                category=normalise_official_category(source_class),
                source_class=source_class[:80],
                name=name[:240] or None,
            )
        )
    if not records:
        raise ValueError(
            f"no polygon features carried the category field {category_field!r}"
        )
    return records

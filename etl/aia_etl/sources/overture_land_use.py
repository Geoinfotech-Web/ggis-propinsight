"""Overture Maps land-use polygons for open planning context.

Overture's land-use feature type is primarily derived from OpenStreetMap. It
describes mapped/observed human use, not statutory AGIS zoning. The publisher
keeps this distinction in every row through ``designation`` and attribution.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from aia_etl.sources.overture import latest_release

log = logging.getLogger(__name__)

DESIGNATION = "observed_reference"
SOURCE_NAME = "Overture Maps / OpenStreetMap"
SOURCE_URL = "https://docs.overturemaps.org/schema/reference/base/land_use/"


@dataclass(frozen=True)
class LandUseRecord:
    source_id: str
    geometry: str
    category: str
    source_class: str | None
    source_subtype: str | None
    name: str | None


def normalise_category(source_class: str | None, subtype: str | None) -> str:
    """Map Overture's detailed taxonomy to stable product categories."""
    cls = (source_class or "").lower()
    sub = (subtype or "").lower()
    if cls == "residential" or sub == "residential":
        return "residential"
    if cls == "industrial":
        return "industrial"
    if cls in {"commercial", "retail"}:
        return "commercial"
    if sub in {"education", "medical", "religious"} or cls in {
        "school",
        "college",
        "university",
        "hospital",
        "clinic",
        "religious",
        "institutional",
    }:
        return "institutional"
    if sub == "protected" or cls in {
        "protected",
        "nature_reserve",
        "strict_nature_reserve",
        "national_park",
        "wilderness_area",
        "species_management_area",
    }:
        return "protected_reserve"
    if sub in {"park", "recreation", "grass", "golf", "entertainment"}:
        return "recreation_open_space"
    if sub in {"agriculture", "horticulture", "aquaculture"}:
        return "agricultural"
    if sub == "military" or cls in {"military", "barracks", "base"}:
        return "military_restricted"
    if sub in {"transportation", "pedestrian"}:
        return "transportation"
    if sub == "construction" or cls in {"construction", "greenfield", "brownfield"}:
        return "construction_development"
    if sub == "resource_extraction" or cls == "quarry":
        return "extractive"
    if sub == "landfill" or cls == "landfill":
        return "landfill"
    if sub == "cemetery" or cls in {"cemetery", "grave_yard"}:
        return "cemetery"
    return "other"


def build_sql(bbox: tuple[float, float, float, float], release: str) -> str:
    min_lon, min_lat, max_lon, max_lat = bbox
    path = (
        f"s3://overturemaps-us-west-2/release/{release}/"
        "theme=base/type=land_use/*.parquet"
    )
    return f"""
        SELECT id, names.primary AS name, class AS source_class,
               subtype AS source_subtype, ST_AsGeoJSON(geometry) AS geometry
        FROM read_parquet('{path}', filename=true, hive_partitioning=1)
        WHERE bbox.xmin <= {max_lon} AND bbox.xmax >= {min_lon}
          AND bbox.ymin <= {max_lat} AND bbox.ymax >= {min_lat}
          AND ST_GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')
    """


def fetch_overture_land_use(
    bbox: tuple[float, float, float, float], release: str
) -> tuple[list[LandUseRecord], str]:
    """Fetch polygonal land-use records and the resolved release."""
    import duckdb

    resolved_release = latest_release() if release.lower() == "latest" else release
    con = duckdb.connect()
    try:
        con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
        con.execute("SET s3_region='us-west-2';")
        rows = con.execute(build_sql(bbox, resolved_release)).fetchall()
    finally:
        con.close()

    records = [
        LandUseRecord(
            source_id=str(source_id),
            geometry=str(geometry),
            category=normalise_category(source_class, source_subtype),
            source_class=source_class,
            source_subtype=source_subtype,
            name=name,
        )
        for source_id, name, source_class, source_subtype, geometry in rows
        if source_id and geometry
    ]
    log.info("Overture land use %s returned %d polygons", resolved_release, len(records))
    return records, resolved_release

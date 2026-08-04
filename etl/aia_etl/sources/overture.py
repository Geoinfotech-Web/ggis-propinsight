"""Overture Maps Places — open POIs beyond OSM.

Overture (Linux Foundation; Meta/Microsoft/Amazon/TomTom) publishes a global,
openly-licensed Places dataset that aggregates many non-OSM sources. It's served
as GeoParquet in public cloud storage and queried directly with DuckDB — no bulk
download, bbox pushdown via the `bbox` column. Overture carries mixed upstream
licenses, so downstream products must preserve its published attribution data.

`duckdb` is imported lazily so the module loads without it; the category mapping
is pure and unit-tested.
"""
from __future__ import annotations

import logging

import httpx

from aia_etl.sources.base import PoiRecord

log = logging.getLogger(__name__)

# Overture primary category -> AIA category. Overture uses a rich taxonomy; we
# map the slugs relevant to AIA's amenity domains.
OVERTURE_CATEGORY_MAP: dict[str, str] = {
    # education
    "school": "school",
    "primary_and_secondary_school": "school",
    "college_and_university": "school",
    "education": "school",
    # health
    "hospital": "hospital",
    "clinic": "hospital",
    "pharmacy": "hospital",
    "doctor": "hospital",
    "health_and_medical": "hospital",
    # markets / retail
    "shopping_center": "market",
    "supermarket": "market",
    "grocery_store": "market",
    "market": "market",
    # finance
    "bank_credit_union": "bank",
    "bank": "bank",
    "atm": "bank",
    # fuel
    "gas_station": "fuel",
    # worship
    "religious_organization": "worship",
    "place_of_worship": "worship",
}


def map_overture_category(primary: str | None) -> str | None:
    if not primary:
        return None
    return OVERTURE_CATEGORY_MAP.get(primary.lower())


def _default_release() -> str:
    from aia_etl.config import get_settings

    return get_settings().overture_release


def latest_release() -> str:
    """Resolve Overture's current release from its official STAC catalog."""
    response = httpx.get("https://stac.overturemaps.org/catalog.json", timeout=30.0)
    response.raise_for_status()
    release = response.json().get("latest")
    if not isinstance(release, str) or not release:
        raise ValueError("Overture STAC catalog did not provide a latest release")
    return release


def build_sql(bbox: tuple[float, float, float, float], release: str) -> str:
    """DuckDB SQL selecting Overture places in bbox with a category we map."""
    min_lon, min_lat, max_lon, max_lat = bbox
    path = (
        f"s3://overturemaps-us-west-2/release/{release}/"
        "theme=places/type=place/*.parquet"
    )
    cats = ", ".join(f"'{c}'" for c in OVERTURE_CATEGORY_MAP)
    return f"""
        SELECT
          names.primary AS name,
          categories.primary AS category,
          ST_X(geometry) AS lon,
          ST_Y(geometry) AS lat
        FROM read_parquet('{path}', filename=true, hive_partitioning=1)
        WHERE bbox.xmin <= {max_lon} AND bbox.xmax >= {min_lon}
          AND bbox.ymin <= {max_lat} AND bbox.ymax >= {min_lat}
          AND categories.primary IN ({cats})
    """


def fetch_overture(
    bbox: tuple[float, float, float, float], release: str | None = None
) -> list[PoiRecord]:
    import duckdb

    release = release or _default_release()
    if release.lower() == "latest":
        release = latest_release()
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute("SET s3_region='us-west-2';")
    log.info("Overture query for bbox %s (release %s)", bbox, release)
    rows = con.execute(build_sql(bbox, release)).fetchall()

    records: list[PoiRecord] = []
    for name, primary, lon, lat in rows:
        category = map_overture_category(primary)
        if category is None or lon is None or lat is None:
            continue
        records.append(
            PoiRecord(lon=float(lon), lat=float(lat), category=category,
                      name=name, source="overture")
        )
    log.info("Overture returned %d rows -> %d POIs", len(rows), len(records))
    return records

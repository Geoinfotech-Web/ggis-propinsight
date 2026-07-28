"""OSM roads & POIs pipeline (TDD §4.6, Phase 1 priority #1).

Flow:
    Geofabrik Nigeria extract → clip to AOI → osm2pgsql (staging tables)
      → extract & categorise POIs → QA gate → publish into `poi`
      → bump `poi` + `roads` layer versions (invalidates dependent scorecards)
      → (OSRM/Valhalla graph rebuild — triggered separately)

Heavy tool orchestration (osm2pgsql, osmium) runs via subprocess; the geometry
work is kept in small functions so the categorisation and QA logic is testable.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer
from aia_etl.poi_categories import categorize
from aia_etl.qa import FCT_BBOX, QAReport, require_geometry, run_rules, valid_category, within_bbox

log = logging.getLogger(__name__)
settings = get_settings()

# osm2pgsql staging table produced from the extract (default output prefix).
_STAGING_POINT = "planet_osm_point"
_STAGING_POLYGON = "planet_osm_polygon"

# OSM tag columns osm2pgsql exposes as hstore/columns that we inspect for POIs.
_POI_TAG_KEYS = ("amenity", "shop", "man_made", "power", "healthcare", "tower:type")


def _run(cmd: list[str]) -> None:
    log.info("run: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def clip_extract(pbf_in: Path, pbf_out: Path, bbox: tuple[float, float, float, float]) -> Path:
    """Clip the national extract to the AOI bbox with osmium (fast, index-free)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    _run([
        "osmium", "extract", "-b",
        f"{min_lon},{min_lat},{max_lon},{max_lat}",
        str(pbf_in), "-o", str(pbf_out), "--overwrite",
    ])
    return pbf_out


def load_osm2pgsql(pbf: Path) -> None:
    """Load the clipped extract into PostGIS staging tables via osm2pgsql."""
    _run([
        "osm2pgsql", "--create", "--slim", "--drop", "--hstore",
        "-d", settings.sync_sqlalchemy_url.replace("postgresql+psycopg", "postgresql"),
        str(pbf),
    ])


def _staging_pois() -> list[dict[str, Any]]:
    """Read candidate POI rows from staging, categorise in Python, keep the hits."""
    tag_cols = ", ".join(f'"{k}"' for k in _POI_TAG_KEYS)
    records: list[dict[str, Any]] = []
    with connect() as conn:
        for table, geom_expr in (
            (_STAGING_POINT, "way"),
            (_STAGING_POLYGON, "ST_Centroid(way)"),
        ):
            rows = conn.execute(
                text(
                    f"""
                    SELECT name, {tag_cols},
                           ST_X(ST_Transform({geom_expr}, 4326)) AS lon,
                           ST_Y(ST_Transform({geom_expr}, 4326)) AS lat
                    FROM {table}
                    WHERE amenity IS NOT NULL OR shop IS NOT NULL
                       OR man_made IS NOT NULL OR power IS NOT NULL
                       OR healthcare IS NOT NULL
                    """
                )
            ).mappings()
            for r in rows:
                tags = {k: r[k] for k in _POI_TAG_KEYS if r.get(k)}
                category = categorize(tags)
                if category is None:
                    continue
                records.append(
                    {"name": r.get("name"), "category": category,
                     "lon": r["lon"], "lat": r["lat"], "source": "osm"}
                )
    return records


def _publish_pois(records: list[dict[str, Any]], layer_version: str) -> int:
    """Replace the OSM-sourced POI layer with the QA-passed records."""
    with connect() as conn:
        conn.execute(text("DELETE FROM poi WHERE source = 'osm'"))
        if records:
            conn.execute(
                text(
                    """
                    INSERT INTO poi (geom, category, name, source, verified, layer_version)
                    VALUES (ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                            :category, :name, 'osm', false, :lv)
                    """
                ),
                [{**r, "lv": layer_version} for r in records],
            )
    return len(records)


def qa_pois(records: list[dict[str, Any]]) -> QAReport:
    return run_rules(
        records,
        [require_geometry, valid_category, within_bbox(FCT_BBOX)],
    )


@app.task(name="aia_etl.tasks.osm.refresh_osm")
def refresh_osm(pbf_path: str | None = None) -> dict[str, Any]:
    """Full monthly OSM refresh for the AOI. Returns a run summary."""
    data = Path(settings.data_dir)
    national = Path(pbf_path) if pbf_path else data / "nigeria-latest.osm.pbf"
    clipped = data / f"{settings.aoi_name.lower()}-latest.osm.pbf"

    clip_extract(national, clipped, FCT_BBOX)
    load_osm2pgsql(clipped)

    candidates = _staging_pois()
    report = qa_pois(candidates)

    with connect() as conn:
        poi_version, poi_invalidated = bump_layer(conn, "poi", source="OSM (Geofabrik)")
        roads_version, roads_invalidated = bump_layer(conn, "roads", source="OSM (Geofabrik)")

    published = _publish_pois(report.passed, poi_version)
    summary = {
        "aoi": settings.aoi_name,
        "poi_version": poi_version,
        "roads_version": roads_version,
        "published_pois": published,
        "qa": report.summary(),
        "scores_invalidated": poi_invalidated + roads_invalidated,
    }
    log.info("refresh_osm complete: %s", summary)
    return summary


@app.task(name="aia_etl.tasks.osm.noop")
def noop() -> str:
    """Placeholder for schedule slots whose task lands in a later phase."""
    return "noop"

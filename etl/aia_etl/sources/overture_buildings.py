"""FCT building footprints from Overture Maps for analytical 3D."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx

from aia_etl.sources.overture import latest_release

log = logging.getLogger(__name__)
SOURCE_NAME = "Overture Maps Buildings"
SOURCE_URL = "https://docs.overturemaps.org/guides/buildings/"
DEFAULT_VISUAL_HEIGHT_M = 6.0
FLOOR_HEIGHT_M = 3.2


@dataclass(frozen=True)
class BuildingRecord:
    source_id: str
    parent_source_id: str | None
    feature_type: str
    geometry: str
    building_class: str | None
    height_m: float | None
    num_floors: int | None
    min_height_m: float | None
    display_height_m: float
    height_basis: str
    source_datasets: tuple[str, ...]


def resolve_display_height(
    height_m: float | None, num_floors: int | None
) -> tuple[float, str]:
    if height_m is not None and height_m > 0:
        return float(height_m), "published_height"
    if num_floors is not None and num_floors > 0:
        return float(num_floors) * FLOOR_HEIGHT_M, "floors_derived"
    return DEFAULT_VISUAL_HEIGHT_M, "default_visual"


def build_sql(bbox: tuple[float, float, float, float], release: str) -> str:
    min_lon, min_lat, max_lon, max_lat = bbox
    path = (
        f"s3://overturemaps-us-west-2/release/{release}/"
        "theme=buildings/type=*/*.parquet"
    )
    return f"""
        SELECT id, type, class, height, num_floors, min_height,
               building_id, has_parts, to_json(sources) AS sources,
               ST_AsGeoJSON(geometry) AS geometry
        FROM read_parquet(
          '{path}', filename=true, hive_partitioning=1, union_by_name=true
        )
        WHERE bbox.xmin <= {max_lon} AND bbox.xmax >= {min_lon}
          AND bbox.ymin <= {max_lat} AND bbox.ymax >= {min_lat}
          AND ST_GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')
          AND ST_IsValid(geometry)
    """


def feature_type_sql(
    bbox: tuple[float, float, float, float],
    release: str,
    feature_type: str,
    *,
    as_geojson: bool = True,
    asset_urls: tuple[str, ...] | None = None,
) -> str:
    if feature_type not in {"building", "building_part"}:
        raise ValueError("feature_type must be building or building_part")
    min_lon, min_lat, max_lon, max_lat = bbox
    paths = asset_urls or (
        f"s3://overturemaps-us-west-2/release/{release}/"
        f"theme=buildings/type={feature_type}/*.parquet",
    )
    path = "'" + paths[0] + "'" if len(paths) == 1 else repr(list(paths))
    building_class = "class" if feature_type == "building" else "CAST(NULL AS VARCHAR)"
    building_id = "CAST(NULL AS VARCHAR)" if feature_type == "building" else "building_id"
    has_parts = "has_parts" if feature_type == "building" else "CAST(NULL AS BOOLEAN)"
    geometry = "ST_AsGeoJSON(geometry)" if as_geojson else "ST_AsWKB(geometry)"
    return f"""
        SELECT id, '{feature_type}' AS type, {building_class} AS class,
               height, num_floors, min_height,
               {building_id} AS building_id, {has_parts} AS has_parts,
               to_json(sources) AS sources,
               {geometry} AS geometry
        FROM read_parquet({path}, filename=true, union_by_name=true)
        WHERE bbox.xmin <= {max_lon} AND bbox.xmax >= {min_lon}
          AND bbox.ymin <= {max_lat} AND bbox.ymax >= {min_lat}
          AND ST_GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')
          AND ST_IsValid(geometry)
    """


def _intersects(
    left: tuple[float, float, float, float], right: tuple[float, float, float, float]
) -> bool:
    return not (
        left[2] < right[0]
        or left[0] > right[2]
        or left[3] < right[1]
        or left[1] > right[3]
    )


def stac_asset_urls(
    bbox: tuple[float, float, float, float], release: str, feature_type: str
) -> tuple[str, ...]:
    """Resolve only Overture Parquet shards whose STAC extents intersect the AOI."""
    collection_url = (
        f"https://stac.overturemaps.org/{release}/buildings/"
        f"{feature_type}/collection.json"
    )
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        collection = client.get(collection_url)
        collection.raise_for_status()
        item_urls = [
            urljoin(collection_url, str(link["href"]))
            for link in collection.json().get("links", [])
            if link.get("rel") == "item" and link.get("href")
        ]

        def matching_asset(url: str) -> str | None:
            response = client.get(url)
            response.raise_for_status()
            item = response.json()
            extent = item.get("bbox")
            if not isinstance(extent, list) or len(extent) < 4:
                return None
            item_bbox = tuple(float(value) for value in extent[:4])
            if not _intersects(bbox, item_bbox):  # type: ignore[arg-type]
                return None
            asset = item.get("assets", {}).get("aws", {}).get("href")
            return str(asset) if asset else None

        with ThreadPoolExecutor(max_workers=12) as executor:
            urls = tuple(url for url in executor.map(matching_asset, item_urls) if url)
    if not urls:
        raise ValueError(f"Overture STAC returned no {feature_type} assets for the AOI")
    log.info("Overture STAC selected %d %s shards for %s", len(urls), feature_type, bbox)
    return urls


def tiled_bboxes(
    bbox: tuple[float, float, float, float], divisions: int = 2
) -> tuple[tuple[float, float, float, float], ...]:
    """Split a large AOI so DuckDB can release scan memory between spatial chunks."""
    if divisions < 1:
        raise ValueError("divisions must be positive")
    min_lon, min_lat, max_lon, max_lat = bbox
    lon_step = (max_lon - min_lon) / divisions
    lat_step = (max_lat - min_lat) / divisions
    return tuple(
        (
            min_lon + column * lon_step,
            min_lat + row * lat_step,
            max_lon if column == divisions - 1 else min_lon + (column + 1) * lon_step,
            max_lat if row == divisions - 1 else min_lat + (row + 1) * lat_step,
        )
        for row in range(divisions)
        for column in range(divisions)
    )


def _source_names(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    names = {
        str(value.get("dataset"))
        for value in values
        if isinstance(value, dict) and value.get("dataset")
    }
    return tuple(sorted(names))


def records_from_rows(rows: list[tuple]) -> list[BuildingRecord]:
    """Prefer valid parts over their parent building to prevent double rendering."""
    part_parent_ids = {
        str(row[6]) for row in rows if row[1] == "building_part" and row[6] and row[9]
    }
    records: list[BuildingRecord] = []
    for (
        source_id,
        feature_type,
        building_class,
        height_m,
        num_floors,
        min_height_m,
        parent_source_id,
        _has_parts,
        sources,
        geometry,
    ) in rows:
        if not source_id or not geometry:
            continue
        if feature_type == "building" and str(source_id) in part_parent_ids:
            continue
        display_height, height_basis = resolve_display_height(height_m, num_floors)
        records.append(
            BuildingRecord(
                source_id=str(source_id),
                parent_source_id=str(parent_source_id) if parent_source_id else None,
                feature_type=str(feature_type),
                geometry=str(geometry),
                building_class=building_class,
                height_m=float(height_m) if height_m is not None else None,
                num_floors=int(num_floors) if num_floors is not None else None,
                min_height_m=float(min_height_m) if min_height_m is not None else None,
                display_height_m=display_height,
                height_basis=height_basis,
                source_datasets=_source_names(sources),
            )
        )
    return records


def fetch_overture_buildings(
    bbox: tuple[float, float, float, float], release: str
) -> tuple[list[BuildingRecord], str]:
    import duckdb

    resolved = latest_release() if release.lower() == "latest" else release
    connection = duckdb.connect()
    try:
        connection.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
        connection.execute("SET s3_region='us-west-2';")
        rows = connection.execute(build_sql(bbox, resolved)).fetchall()
    finally:
        connection.close()
    records = records_from_rows(rows)
    log.info("Overture buildings %s returned %d renderable features", resolved, len(records))
    return records, resolved


def iter_overture_building_batches(
    bbox: tuple[float, float, float, float],
    release: str,
    *,
    batch_size: int = 1_000,
) -> tuple[str, Iterator[list[BuildingRecord]]]:
    """Stream parts first, then parents without valid parts, to bound worker memory."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    resolved = latest_release() if release.lower() == "latest" else release
    assets = {
        feature_type: stac_asset_urls(bbox, resolved, feature_type)
        for feature_type in ("building_part", "building")
    }

    def batches() -> Iterator[list[BuildingRecord]]:
        import duckdb

        # A force-stopped worker cannot execute the generator's ``finally`` block.
        # Remove only this importer's well-scoped spill files before a new run.
        for stale_path in Path(tempfile.gettempdir()).glob("overture-*.parquet"):
            if stale_path.name.startswith(("overture-building-", "overture-building_part-")):
                stale_path.unlink(missing_ok=True)

        part_parent_ids: set[str] = set()
        seen_source_ids: set[str] = set()

        def query(
            tile: tuple[float, float, float, float], feature_type: str
        ) -> Iterator[list[tuple]]:
            descriptor, spill_path = tempfile.mkstemp(
                prefix=f"overture-{feature_type}-", suffix=".parquet"
            )
            os.close(descriptor)
            os.unlink(spill_path)
            connection = duckdb.connect()
            try:
                connection.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
                connection.execute("SET s3_region='us-west-2';")
                connection.execute("SET memory_limit='512MB';")
                connection.execute("SET temp_directory='/tmp/overture-buildings';")
                connection.execute("SET threads=2;")
                source_sql = feature_type_sql(
                    tile,
                    resolved,
                    feature_type,
                    as_geojson=False,
                    asset_urls=assets[feature_type],
                )
                connection.execute(
                    f"COPY ({source_sql}) TO '{spill_path}' "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)"
                )
            finally:
                connection.close()

            local = duckdb.connect()
            try:
                local.execute("INSTALL spatial; LOAD spatial;")
                result = local.execute(
                    """
                    SELECT id, type, class, height, num_floors, min_height,
                           building_id, has_parts, to_json(sources) AS sources,
                           ST_AsGeoJSON(ST_GeomFromWKB(geometry)) AS geometry
                    FROM read_parquet(?)
                    """,
                    [spill_path],
                )
                while rows := result.fetchmany(batch_size):
                    yield rows
            finally:
                local.close()
                os.unlink(spill_path)

        # STAC already prunes the global catalogue to the few shards touching FCT;
        # one COPY per feature type avoids re-reading those remote shards per tile.
        tiles = tiled_bboxes(bbox, divisions=1)
        for tile in tiles:
            for rows in query(tile, "building_part"):
                records = [
                    record
                    for record in records_from_rows(rows)
                    if record.source_id not in seen_source_ids
                ]
                part_parent_ids.update(
                    record.parent_source_id
                    for record in records
                    if record.parent_source_id is not None
                )
                seen_source_ids.update(record.source_id for record in records)
                if records:
                    yield records

        for tile in tiles:
            for rows in query(tile, "building"):
                records = [
                    record
                    for record in records_from_rows(rows)
                    if record.source_id not in part_parent_ids
                    and record.source_id not in seen_source_ids
                ]
                seen_source_ids.update(record.source_id for record in records)
                if records:
                    yield records

    return resolved, batches()

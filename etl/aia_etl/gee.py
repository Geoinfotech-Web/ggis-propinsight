"""Google Earth Engine integration — DEM and remote-sensing analysis (Overview §6.3).

Auth is service-account based (GEE_SERVICE_ACCOUNT_EMAIL + GEE_SERVICE_ACCOUNT_KEY).
The key value may be either a path to the JSON key file or the JSON content itself.
`earthengine-api` is imported lazily so this module loads without it present, and
the "not configured" path raises before any EE import.

Exports use `getDownloadURL`, which caps at a few tens of MB. For an AOI larger
than that (e.g. all of FCT at 30 m) tile the AOI or export to GCS — see
`export_dem_cop30`'s note.
"""
from __future__ import annotations

import logging
import math
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from aia_etl.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

BBox = tuple[float, float, float, float]

COPERNICUS_DEM_ASSET = "COPERNICUS/DEM/GLO30_2024_1"
GHSL_POPULATION_ASSET = "JRC/GHSL/P2023A/GHS_POP"
GHSL_BUILT_SURFACE_ASSET = "JRC/GHSL/P2023A/GHS_BUILT_S"
DYNAMIC_WORLD_ASSET = "GOOGLE/DYNAMICWORLD/V1"
LANDSAT_L2_ASSETS = (
    "LANDSAT/LC08/C02/T1_L2",
    "LANDSAT/LC09/C02/T1_L2",
)
ENVIRONMENT_BANDS = (
    "population_2025",
    "population_2030",
    "built_surface_2025_m2",
    "built_surface_2030_m2",
    "green_share",
    "built_bare_share",
    "surface_temp_c",
)

_initialised = False


def _project_from_email(email: str) -> str | None:
    """Parse the Cloud project from a service-account email.

    >>> _project_from_email("aia-etl@ggis-propinsight.iam.gserviceaccount.com")
    'ggis-propinsight'
    """
    try:
        domain = email.split("@", 1)[1]
        if domain.endswith(".iam.gserviceaccount.com"):
            return domain.split(".", 1)[0]
    except IndexError:
        return None
    return None


def init_ee() -> None:
    """Initialise Earth Engine with the configured service account (idempotent)."""
    global _initialised
    if _initialised:
        return

    email = settings.gee_service_account_email
    key = settings.gee_service_account_key
    if not email or not key:
        raise RuntimeError(
            "GEE not configured: set GEE_SERVICE_ACCOUNT_EMAIL and GEE_SERVICE_ACCOUNT_KEY"
        )

    import ee  # lazy — only needed when actually talking to EE

    if key.strip().startswith("{"):
        creds = ee.ServiceAccountCredentials(email, key_data=key)
    elif Path(key).exists():
        creds = ee.ServiceAccountCredentials(email, key_file=key)
    else:
        # Treat as JSON content that simply isn't brace-prefixed by whitespace.
        creds = ee.ServiceAccountCredentials(email, key_data=key)

    project = settings.gee_project or _project_from_email(email)
    ee.Initialize(creds, project=project)
    _initialised = True
    log.info("Earth Engine initialised (project=%s)", project)


def _download(url: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{out_path.name}.", suffix=".partial", dir=out_path.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with requests.get(url, stream=True, timeout=600) as response:
            if not response.ok:
                detail = response.text[:1_000].strip()
                raise RuntimeError(
                    f"Earth Engine download failed with HTTP {response.status_code}: {detail}"
                )
            with temporary.open("wb") as stream:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    stream.write(chunk)
        if temporary.stat().st_size == 0:
            raise RuntimeError("Earth Engine returned an empty download")
        temporary.replace(out_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return out_path


def _export_dem_tile(bbox: BBox, out_path: Path, scale: int) -> Path:
    init_ee()
    import ee

    region = ee.Geometry.Rectangle(list(bbox))
    dem = ee.ImageCollection(COPERNICUS_DEM_ASSET).select("DEM").mosaic().clip(region)
    url = dem.getDownloadURL(
        {
            "region": region,
            "format": "GEO_TIFF",
            "crs": "EPSG:32632",
            "crs_transform": [scale, 0, 0, 0, -scale, 0],
        }
    )
    return _download(url, out_path)


def export_dem_cop30(bbox: BBox, out_path: Path, scale: int = 30) -> Path:
    """Export a tiled current Copernicus GLO-30 DEM mosaic for the AOI."""
    from aia_etl.sources.rasters import merge_rasters

    tiles = _bbox_tiles(bbox)
    log.info(
        "exporting Copernicus GLO-30 DEM for %s at %sm in %s tile(s)",
        bbox,
        scale,
        len(tiles),
    )
    if len(tiles) == 1:
        return _export_dem_tile(bbox, out_path, scale)
    tile_dir = out_path.parent / f".{out_path.stem}-tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)

    def export(index_and_bbox: tuple[int, BBox]) -> Path:
        index, tile_bbox = index_and_bbox
        return _export_dem_tile(
            tile_bbox, tile_dir / f"tile-{index:02d}.tif", scale
        )

    with ThreadPoolExecutor(max_workers=min(4, len(tiles))) as executor:
        paths = list(executor.map(export, enumerate(tiles)))
    merged = merge_rasters(paths, out_path)
    for path in paths:
        path.unlink(missing_ok=True)
    tile_dir.rmdir()
    return merged


def _complete_dry_seasons(today: date) -> list[tuple[date, date]]:
    """Return the three most recent complete November-to-March dry seasons."""
    latest_end_year = today.year if today >= date(today.year, 3, 31) else today.year - 1
    return [
        (date(end_year - 1, 11, 1), date(end_year, 4, 1))
        for end_year in range(latest_end_year - 2, latest_end_year + 1)
    ]


def _landsat_surface_temperature(region: Any, today: date) -> tuple[Any, str]:
    """Cloud-mask and composite three complete dry seasons as surface temperature."""
    import ee

    def mask_and_scale(image: Any) -> Any:
        # QA_PIXEL bits 0..5 are fill, dilated cloud, cirrus, cloud, shadow and snow.
        clear = image.select("QA_PIXEL").bitwiseAnd(0b11_1111).eq(0)
        temperature = image.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15)
        return temperature.updateMask(clear).updateMask(image.select("ST_B10").gt(0))

    seasons = _complete_dry_seasons(today)
    composites = []
    native_projection = None
    for start, end_exclusive in seasons:
        collection = ee.ImageCollection(LANDSAT_L2_ASSETS[0])
        for asset in LANDSAT_L2_ASSETS[1:]:
            collection = collection.merge(ee.ImageCollection(asset))
        collection = (
            collection.filterBounds(region)
            .filterDate(start.isoformat(), end_exclusive.isoformat())
            .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
            .map(mask_and_scale)
        )
        if native_projection is None:
            native_projection = ee.Image(collection.first()).select("ST_B10").projection()
        composites.append(collection.median().setDefaultProjection(native_projection))
    last_complete_day = seasons[-1][1] - timedelta(days=1)
    period = f"{seasons[0][0]:%Y-%m} to {last_complete_day:%Y-%m}"
    composite = (
        ee.ImageCollection.fromImages(composites)
        .median()
        .setDefaultProjection(native_projection)
        .rename("surface_temp_c")
    )
    return composite, period


def build_environmental_stack(
    bbox: BBox,
    *,
    today: date | None = None,
    scale: int = 250,
) -> tuple[Any, str]:
    """Build the query-ready FCT environmental stack from public EE datasets."""
    init_ee()
    import ee

    current_date = today or date.today()
    region = ee.Geometry.Rectangle(list(bbox))
    population = [
        ee.Image(f"{GHSL_POPULATION_ASSET}/{epoch}")
        .select("population_count")
        .reduceResolution(reducer=ee.Reducer.sum(), maxPixels=4096)
        .rename(f"population_{epoch}")
        for epoch in (2025, 2030)
    ]
    built = [
        ee.Image(f"{GHSL_BUILT_SURFACE_ASSET}/{epoch}")
        .select("built_surface")
        .reduceResolution(reducer=ee.Reducer.sum(), maxPixels=4096)
        .rename(f"built_surface_{epoch}_m2")
        for epoch in (2025, 2030)
    ]

    cover_end = current_date.replace(day=1)
    cover_start = date(cover_end.year - 1, cover_end.month, 1)
    cover_collection = (
        ee.ImageCollection(DYNAMIC_WORLD_ASSET)
        .filterBounds(region)
        .filterDate(cover_start.isoformat(), cover_end.isoformat())
        .select("label")
    )
    cover_projection = ee.Image(cover_collection.first()).select("label").projection()
    labels = cover_collection.mode().setDefaultProjection(cover_projection)
    green = (
        labels.eq(1)
        .Or(labels.eq(2))
        .Or(labels.eq(5))
        .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=4096)
        .rename("green_share")
    )
    pressure = (
        labels.eq(6)
        .Or(labels.eq(7))
        .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=4096)
        .rename("built_bare_share")
    )
    heat, heat_period = _landsat_surface_temperature(region, current_date)
    heat = heat.reduceResolution(reducer=ee.Reducer.mean(), maxPixels=4096)

    stack = ee.Image.cat([*population, *built, green, pressure, heat]).toFloat().clip(region)
    return stack, heat_period


def export_environmental_stack(
    bbox: BBox,
    out_path: Path,
    *,
    scale: int = 250,
    today: date | None = None,
) -> tuple[Path, str]:
    """Export the seven-band environmental stack as one bounded local GeoTIFF."""
    import ee

    image, heat_period = build_environmental_stack(bbox, today=today, scale=scale)
    region = ee.Geometry.Rectangle(list(bbox))
    url = image.getDownloadURL(
        {
            "bands": list(ENVIRONMENT_BANDS),
            "region": region,
            "format": "GEO_TIFF",
            "filePerBand": False,
            "crs": "EPSG:32632",
            "crs_transform": [scale, 0, 0, 0, -scale, 0],
        }
    )
    log.info("exporting Earth Engine environmental stack for %s at %sm", bbox, scale)
    return _download(url, out_path), heat_period


def _bbox_tiles(bbox: BBox, max_span_degrees: float = 0.55) -> list[BBox]:
    """Split a lon/lat bbox into deterministic bounded export regions."""
    if max_span_degrees <= 0:
        raise ValueError("tile span must be positive")
    west, south, east, north = bbox
    columns = max(1, math.ceil((east - west) / max_span_degrees))
    rows = max(1, math.ceil((north - south) / max_span_degrees))
    width = (east - west) / columns
    height = (north - south) / rows
    return [
        (
            west + column * width,
            south + row * height,
            west + (column + 1) * width,
            south + (row + 1) * height,
        )
        for row in range(rows)
        for column in range(columns)
    ]


def export_environmental_stack_tiled(
    bbox: BBox,
    out_path: Path,
    *,
    scale: int = 250,
    today: date | None = None,
    max_span_degrees: float = 0.55,
    max_workers: int = 4,
) -> tuple[Path, str]:
    """Export bounded tiles concurrently and atomically mosaic the FCT stack."""
    from aia_etl.sources.rasters import merge_rasters

    init_ee()
    tiles = _bbox_tiles(bbox, max_span_degrees)
    tile_dir = out_path.parent / f".{out_path.stem}-tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)

    def export(index_and_bbox: tuple[int, BBox]) -> tuple[Path, str]:
        index, tile_bbox = index_and_bbox
        return export_environmental_stack(
            tile_bbox,
            tile_dir / f"tile-{index:02d}.tif",
            scale=scale,
            today=today,
        )

    with ThreadPoolExecutor(max_workers=min(max_workers, len(tiles))) as executor:
        results = list(executor.map(export, enumerate(tiles)))
    periods = {period for _, period in results}
    if len(periods) != 1:
        raise RuntimeError("Earth Engine tiles returned inconsistent data periods")
    paths = [path for path, _ in results]
    merged = merge_rasters(paths, out_path)
    for path in paths:
        path.unlink(missing_ok=True)
    tile_dir.rmdir()
    return merged, periods.pop()


def export_s2_composite(
    bbox: BBox, out_path: Path, start: str, end: str, scale: int = 10, max_cloud: int = 20
) -> Path:
    """Export a cloud-masked Sentinel-2 median composite (RGB+NIR) for the AOI.

    Feeds later analysis (vegetation/NDVI for environmental nuisance & feasibility).
    """
    init_ee()
    import ee

    region = ee.Geometry.Rectangle(list(bbox))

    def _mask(img: Any) -> Any:
        scl = img.select("SCL")
        keep = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return img.updateMask(keep)

    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        .map(_mask)
    )
    composite = coll.median().select(["B4", "B3", "B2", "B8"]).clip(region)
    url = composite.getDownloadURL(
        {"region": region, "scale": scale, "format": "GEO_TIFF", "crs": "EPSG:4326"}
    )
    log.info("exporting Sentinel-2 composite %s..%s for %s", start, end, bbox)
    return _download(url, out_path)


def export_dynamic_world_mode(
    bbox: BBox,
    out_path: Path,
    start: str,
    end: str,
    scale: int = 30,
) -> Path:
    """Export the modal Dynamic World class for a period as one categorical raster."""
    init_ee()
    import ee

    region = ee.Geometry.Rectangle(list(bbox))
    labels = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(region)
        .filterDate(start, end)
        .select("label")
        .mode()
        .rename("label")
        .clip(region)
    )
    url = labels.getDownloadURL(
        {"region": region, "scale": scale, "format": "GEO_TIFF", "crs": "EPSG:4326"}
    )
    log.info("exporting Dynamic World modal cover %s..%s for %s", start, end, bbox)
    return _download(url, out_path)

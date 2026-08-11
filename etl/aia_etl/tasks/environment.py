"""Direct-source environmental, population and settlement processing for FCT."""
from __future__ import annotations

import json
import logging
import math
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer, next_layer_version
from aia_etl.sources.rasters import (
    download_file,
    select_asset,
    sha256_file,
    signed_planetary_computer_href,
    stac_items,
)

log = logging.getLogger(__name__)
settings = get_settings()
TARGET_CRS = "EPSG:32632"
CELL_SIZE_M = 250
LANDSAT_SCALE = 0.00341802
LANDSAT_OFFSET_K = 149.0


def landsat_surface_temperature_c(values: Any) -> Any:
    """Apply the documented Landsat Collection 2 Level-2 ST scale and offset."""
    return values * LANDSAT_SCALE + LANDSAT_OFFSET_K - 273.15


def landsat_clear_mask(qa_values: Any) -> Any:
    """True without fill, dilated cloud, cirrus, cloud, shadow, or snow flags."""
    return (qa_values.astype("uint16") & 0b11_1111) == 0


def percentile_ranks(values: Any) -> Any:
    """Return 0..100 empirical percentile ranks while preserving NaN cells."""
    import numpy as np

    array = np.asarray(values, dtype="float64")
    result = np.full(array.shape, np.nan, dtype="float32")
    valid = np.isfinite(array)
    if not valid.any():
        return result
    order = np.argsort(array[valid], kind="mergesort")
    ranks = np.empty(order.size, dtype="float32")
    ranks[order] = np.linspace(0.0, 100.0, order.size, dtype="float32")
    result[valid] = ranks
    return result


def migration_components(
    population_2025: Any,
    population_2030: Any,
    built_now: Any,
    built_2030: Any,
):
    """Cell changes and FCT-relative percentiles used by the API migration proxy."""
    import numpy as np

    pop_change_pct = np.full_like(population_2025, np.nan, dtype="float64")
    np.divide(
        100.0 * (population_2030 - population_2025),
        population_2025,
        out=pop_change_pct,
        where=population_2025 > 0,
    )
    built_change_pct = np.where(built_2030 > 0, 100.0, 0.0).astype("float64")
    np.divide(
        100.0 * (built_2030 - built_now),
        built_now,
        out=built_change_pct,
        where=built_now > 0,
    )
    return (
        built_change_pct,
        percentile_ranks(pop_change_pct),
        percentile_ranks(built_change_pct),
    )


def _latest_three_complete_dry_seasons(today: date) -> tuple[date, date, str]:
    """Abuja dry seasons are represented as November through March."""
    latest_end_year = today.year if today >= date(today.year, 3, 31) else today.year - 1
    end = date(latest_end_year, 3, 31)
    start = date(latest_end_year - 3, 11, 1)
    return start, end, f"{start:%Y-%m} to {end:%Y-%m} (three complete dry seasons)"


def _complete_dry_seasons(today: date) -> list[tuple[date, date]]:
    latest_end_year = today.year if today >= date(today.year, 3, 31) else today.year - 1
    return [
        (date(end_year - 1, 11, 1), date(end_year, 3, 31))
        for end_year in range(latest_end_year - 2, latest_end_year + 1)
    ]


def _target_grid(bbox: tuple[float, float, float, float]):
    from rasterio.transform import from_origin
    from rasterio.warp import transform_bounds

    left, bottom, right, top = transform_bounds("EPSG:4326", TARGET_CRS, *bbox)
    width = math.ceil((right - left) / CELL_SIZE_M)
    height = math.ceil((top - bottom) / CELL_SIZE_M)
    return from_origin(left, top, CELL_SIZE_M, CELL_SIZE_M), width, height


def _warp(path: Path, transform: Any, width: int, height: int, *, sum_values: bool = False):
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    destination = np.full((height, width), np.nan, dtype="float32")
    with rasterio.open(path) as source:
        reproject(
            source=rasterio.band(source, 1),
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=transform,
            dst_crs=TARGET_CRS,
            dst_nodata=np.nan,
            resampling=Resampling.sum if sum_values else Resampling.bilinear,
        )
    return destination


def _land_cover_fractions(path: Path, transform: Any, width: int, height: int):
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    with rasterio.open(path) as source:
        values = source.read(1)
        # ESA WorldCover: tree=10, shrub=20, grass=30; built=50, bare=60.
        green_source = np.isin(values, (10, 20, 30)).astype("float32")
        pressure_source = np.isin(values, (50, 60)).astype("float32")
        outputs = []
        for data in (green_source, pressure_source):
            target = np.full((height, width), np.nan, dtype="float32")
            reproject(
                source=data,
                destination=target,
                src_transform=source.transform,
                src_crs=source.crs,
                src_nodata=None,
                dst_transform=transform,
                dst_crs=TARGET_CRS,
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
            outputs.append(np.clip(target, 0.0, 1.0))
    return outputs[0], outputs[1]


def _landsat_composite(
    bbox: tuple[float, float, float, float], transform: Any, width: int, height: int
):
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    start, end, period = _latest_three_complete_dry_seasons(date.today())
    season_composites: list[Any] = []
    scene_dir = Path(settings.data_dir) / "surface_heat" / "source"
    for season_start, season_end in _complete_dry_seasons(date.today()):
        items = stac_items(
            settings.usgs_landsat_stac_url,
            collection=settings.usgs_landsat_st_collection,
            bbox=bbox,
            datetime_range=(
                f"{season_start.isoformat()}T00:00:00Z/"
                f"{season_end.isoformat()}T23:59:59Z"
            ),
            limit=100,
        )
        usable = []
        for item in items:
            cloud = item.get("properties", {}).get("eo:cloud_cover")
            if isinstance(cloud, (int, float)) and cloud > 40:
                continue
            usable.append(item)
        usable.sort(
            key=lambda item: float(
                item.get("properties", {}).get("eo:cloud_cover") or 100.0
            )
        )
        scenes: list[Any] = []
        # A bounded set of the clearest scenes keeps annual refreshes predictable
        # while preserving a cloud-masked median for each complete dry season.
        for item in usable[:12]:
            scene_id = str(item.get("id"))
            temp_path = download_file(
                signed_planetary_computer_href(
                    select_asset(
                        item,
                        ("lwir11", "temperature", "ST_B10", "st", "surface_temperature"),
                    ),
                    settings.planetary_computer_sign_url,
                ),
                scene_dir / f"{scene_id}_st.tif",
            )
            qa_path = download_file(
                signed_planetary_computer_href(
                    select_asset(item, ("qa_pixel", "QA_PIXEL", "qa")),
                    settings.planetary_computer_sign_url,
                ),
                scene_dir / f"{scene_id}_qa.tif",
            )
            temp = np.full((height, width), np.nan, dtype="float32")
            qa = np.full((height, width), 65_535, dtype="uint16")
            with rasterio.open(temp_path) as source:
                reproject(
                    rasterio.band(source, 1), temp,
                    src_transform=source.transform, src_crs=source.crs,
                    dst_transform=transform, dst_crs=TARGET_CRS,
                    dst_nodata=np.nan, resampling=Resampling.bilinear,
                )
            with rasterio.open(qa_path) as source:
                reproject(
                    rasterio.band(source, 1), qa,
                    src_transform=source.transform, src_crs=source.crs,
                    dst_transform=transform, dst_crs=TARGET_CRS,
                    dst_nodata=65_535, resampling=Resampling.nearest,
                )
            temp = landsat_surface_temperature_c(temp)
            temp[~landsat_clear_mask(qa)] = np.nan
            scenes.append(temp)
        if not scenes:
            raise RuntimeError(
                "USGS Landsat STAC returned no usable clear surface-temperature "
                f"scenes for {season_start:%Y-%m} to {season_end:%Y-%m}"
            )
        season_composites.append(np.nanmedian(np.stack(scenes), axis=0))
    if len(season_composites) != 3:
        raise RuntimeError("three complete Landsat dry-season composites are required")
    return (
        np.nanmedian(np.stack(season_composites), axis=0).astype("float32"),
        period,
    )


def _write_raster(path: Path, data: Any, transform: Any) -> Path:
    import rasterio

    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff", "height": data.shape[0], "width": data.shape[1],
        "count": 1, "dtype": "float32", "crs": TARGET_CRS,
        "transform": transform, "nodata": float("nan"), "compress": "deflate",
        "tiled": True,
    }
    partial = path.with_suffix(".partial.tif")
    partial.unlink(missing_ok=True)
    with rasterio.open(partial, "w", **profile) as output:
        output.write(data.astype("float32"), 1)
    partial.replace(path)
    return path


def _download_configured_raster(url: str, source_dir: Path, name: str) -> Path:
    """Download a direct GeoTIFF or select the requested epoch from a ZIP package."""
    if not url.lower().split("?", 1)[0].endswith(".zip"):
        return download_file(url, source_dir / f"{name}.tif")
    archive = download_file(url, source_dir / f"{name}.zip")
    epoch = "2025" if "2025" in name else "2030" if "2030" in name else None
    with zipfile.ZipFile(archive) as package:
        candidates = [
            member for member in package.namelist()
            if member.lower().endswith((".tif", ".tiff"))
            and (epoch is None or epoch in Path(member).name)
        ]
        if not candidates:
            all_rasters = [
                member
                for member in package.namelist()
                if member.lower().endswith((".tif", ".tiff"))
            ]
            if len(all_rasters) == 1:
                candidates = all_rasters
        if not candidates:
            raise RuntimeError(f"{archive.name} has no GeoTIFF matching epoch {epoch or 'any'}")
        if len(candidates) > 1:
            raise RuntimeError(
                f"{archive.name} contains multiple rasters for {epoch or 'the configured metric'}; "
                "configure a direct FCT tile or a single-raster package"
            )
        member = candidates[0]
        destination = source_dir / f"{name}.tif"
        partial = destination.with_suffix(".partial.tif")
        partial.unlink(missing_ok=True)
        with package.open(member) as source, partial.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
        partial.replace(destination)
    return destination


def register_analysis_raster(
    conn: Connection,
    *,
    metric: str,
    epoch: str | None,
    source: str,
    source_url: str,
    path: Path,
    resolution_m: int,
    licence: str,
    layer_version: str,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO analysis_rasters
              (metric, epoch, source, source_url, raster_path, resolution_m,
               checksum_sha256, licence, layer_version)
            VALUES
              (:metric, :epoch, :source, :source_url, :path, :resolution_m,
               :checksum, :licence, :layer_version)
            """
        ),
        {
            "metric": metric, "epoch": epoch, "source": source,
            "source_url": source_url, "path": str(path), "resolution_m": resolution_m,
            "checksum": sha256_file(path), "licence": licence,
            "layer_version": layer_version,
        },
    )


def _cell_records(
    transform: Any,
    arrays: dict[str, Any],
    layer_versions: dict[str, str],
    period: str,
):
    import numpy as np

    height, width = next(iter(arrays.values())).shape
    records: list[dict[str, Any]] = []
    for row in range(height):
        for col in range(width):
            values = {name: float(data[row, col]) for name, data in arrays.items()}
            if not any(np.isfinite(value) for value in values.values()):
                continue
            left, top = transform * (col, row)
            right, bottom = transform * (col + 1, row + 1)
            records.append(
                {
                    "cell_id": f"fct-250-{row}-{col}", "left": left, "bottom": bottom,
                    "right": right, "top": top,
                    **{key: value if np.isfinite(value) else None for key, value in values.items()},
                    "layer_versions": json.dumps(layer_versions), "data_period": period,
                }
            )
    return records


def publish_metric_cells(conn: Connection, records: list[dict[str, Any]]) -> int:
    if not records:
        raise ValueError("environmental processing produced no metric cells")
    conn.execute(text("DELETE FROM spatial_metric_cells"))
    statement = text(
        """
        INSERT INTO spatial_metric_cells (
          cell_id, geom, population_2025, population_2030,
          population_growth_percentile, built_share_current, built_change_pct,
          settlement_growth_percentile, green_share, built_bare_share,
          surface_temp_c, heat_percentile, layer_versions, data_period
        ) VALUES (
          :cell_id,
          ST_Transform(ST_MakeEnvelope(:left, :bottom, :right, :top, 32632), 4326),
          :population_2025, :population_2030, :population_growth_percentile,
          :built_share_current, :built_change_pct, :settlement_growth_percentile,
          :green_share, :built_bare_share, :surface_temp_c, :heat_percentile,
          CAST(:layer_versions AS jsonb), :data_period
        )
        """
    )
    for start in range(0, len(records), 2_000):
        conn.execute(statement, records[start : start + 2_000])
    return len(records)


def _refresh_environmental_metrics_direct(
    bbox: list[float] | None = None,
) -> dict[str, Any]:
    """Publish environmental cells from configured direct-download sources."""
    import numpy as np

    from aia_etl.qa import FCT_BBOX

    required_urls = {
        "worldpop_2025": settings.worldpop_2025_url,
        "ghsl_population_2025": settings.ghsl_population_2025_url,
        "ghsl_population_2030": settings.ghsl_population_2030_url,
        "ghsl_current": settings.ghsl_built_current_url,
        "ghsl_2030": settings.ghsl_built_2030_url,
    }
    missing = [name for name, url in required_urls.items() if not url]
    if missing:
        raise RuntimeError(f"direct raster URL configuration missing: {', '.join(missing)}")
    aoi = tuple(bbox) if bbox else FCT_BBOX
    transform, width, height = _target_grid(aoi)
    source_dir = Path(settings.data_dir) / "environment" / "source"
    paths = {
        name: _download_configured_raster(str(url), source_dir, name)
        for name, url in required_urls.items()
    }
    with connect() as conn:
        land_cover_path = conn.execute(
            text("SELECT raster_path FROM land_cover_rasters ORDER BY created_at DESC LIMIT 1")
        ).scalar()
        versions = {
            layer: next_layer_version(conn, layer)
            for layer in ("population", "settlement", "surface_heat")
        }
    if not land_cover_path:
        raise RuntimeError("published ESA WorldCover raster is required for Livability")

    population_2025 = _warp(paths["worldpop_2025"], transform, width, height, sum_values=True)
    ghsl_population_2025 = _warp(
        paths["ghsl_population_2025"], transform, width, height, sum_values=True
    )
    ghsl_population_2030 = _warp(
        paths["ghsl_population_2030"], transform, width, height, sum_values=True
    )
    ghsl_growth_ratio = np.full_like(ghsl_population_2025, np.nan, dtype="float32")
    np.divide(
        ghsl_population_2030,
        ghsl_population_2025,
        out=ghsl_growth_ratio,
        where=ghsl_population_2025 > 0,
    )
    population_2030 = population_2025 * ghsl_growth_ratio
    built_now_m2 = _warp(paths["ghsl_current"], transform, width, height, sum_values=True)
    built_2030_m2 = _warp(paths["ghsl_2030"], transform, width, height, sum_values=True)
    built_now = np.clip(built_now_m2 / (CELL_SIZE_M**2), 0.0, 1.0)
    built_2030 = np.clip(built_2030_m2 / (CELL_SIZE_M**2), 0.0, 1.0)
    built_change, pop_percentile, settlement_percentile = migration_components(
        population_2025, population_2030, built_now, built_2030
    )
    green, built_bare = _land_cover_fractions(
        Path(land_cover_path), transform, width, height
    )
    heat, period = _landsat_composite(aoi, transform, width, height)
    heat_percentile = percentile_ranks(heat) / 100.0
    heat_path = _write_raster(
        Path(settings.data_dir) / "surface_heat" / f"surface_heat_{versions['surface_heat']}.tif",
        heat,
        transform,
    )
    arrays = {
        "population_2025": population_2025,
        "population_2030": population_2030,
        "population_growth_percentile": pop_percentile,
        "built_share_current": built_now,
        "built_change_pct": built_change,
        "settlement_growth_percentile": settlement_percentile,
        "green_share": green,
        "built_bare_share": built_bare,
        "surface_temp_c": heat,
        "heat_percentile": heat_percentile,
    }
    records = _cell_records(transform, arrays, versions, period)

    with connect() as conn:
        count = publish_metric_cells(conn, records)
        register_analysis_raster(
            conn, metric="surface_temperature", epoch=period,
            source="USGS Landsat Collection 2 Level-2",
            source_url=settings.usgs_landsat_stac_url, path=heat_path,
            resolution_m=CELL_SIZE_M, licence="USGS public domain",
            layer_version=versions["surface_heat"],
        )
        for metric, epoch, source, source_url, path, layer in (
            (
                "population", "2025", "WorldPop Nigeria", str(settings.worldpop_2025_url),
                paths["worldpop_2025"], "population",
            ),
            (
                "population_projection_factor", "2025-2030", "European Commission GHSL",
                str(settings.ghsl_population_2030_url), paths["ghsl_population_2030"],
                "population",
            ),
            (
                "built_surface", "current", "European Commission GHSL",
                str(settings.ghsl_built_current_url), paths["ghsl_current"], "settlement",
            ),
            (
                "built_surface", "2030", "European Commission GHSL",
                str(settings.ghsl_built_2030_url), paths["ghsl_2030"], "settlement",
            ),
        ):
            register_analysis_raster(
                conn, metric=metric, epoch=epoch, source=source, source_url=source_url,
                path=path, resolution_m=100, licence="Open with source attribution",
                layer_version=versions[layer],
            )
        invalidated = 0
        for layer, source in (
            ("population", "WorldPop Nigeria 2025 release"),
            ("settlement", "European Commission GHSL"),
            ("surface_heat", "USGS Landsat Collection 2 Level-2"),
        ):
            published, swept = bump_layer(conn, layer, source=source)
            if published != versions[layer]:
                raise RuntimeError(f"{layer} version changed during publication")
            invalidated += swept
    return {
        "status": "published", "cell_count": count, "layer_versions": versions,
        "data_period": period, "scores_invalidated": invalidated, "source_mode": "direct",
    }


def _read_gee_stack(path: Path) -> tuple[Any, dict[str, Any]]:
    """Read and validate the fixed-order Earth Engine environmental stack."""
    import numpy as np
    import rasterio

    from aia_etl.gee import ENVIRONMENT_BANDS

    with rasterio.open(path) as source:
        if source.count != len(ENVIRONMENT_BANDS):
            raise RuntimeError(
                f"Earth Engine stack has {source.count} bands; expected {len(ENVIRONMENT_BANDS)}"
            )
        data = source.read(masked=True).astype("float32")
        arrays = {
            name: np.asarray(data[index].filled(np.nan), dtype="float32")
            for index, name in enumerate(ENVIRONMENT_BANDS)
        }
        return source.transform, arrays


def _refresh_environmental_metrics_gee(
    bbox: list[float] | None = None,
) -> dict[str, Any]:
    """Publish local metric cells from a bounded Earth Engine export."""
    import numpy as np

    from aia_etl.gee import (
        DYNAMIC_WORLD_ASSET,
        GHSL_BUILT_SURFACE_ASSET,
        GHSL_POPULATION_ASSET,
        LANDSAT_L2_ASSETS,
        export_environmental_stack_tiled,
    )
    from aia_etl.qa import FCT_BBOX

    aoi = tuple(bbox) if bbox else FCT_BBOX
    with connect() as conn:
        versions = {
            layer: next_layer_version(conn, layer)
            for layer in ("population", "settlement", "surface_heat")
        }
    stack_path = (
        Path(settings.data_dir)
        / "environment"
        / f"environment_gee_{versions['surface_heat']}.tif"
    )
    stack_path, period = export_environmental_stack_tiled(
        aoi, stack_path, scale=CELL_SIZE_M
    )
    transform, exported = _read_gee_stack(stack_path)

    population_2025 = exported["population_2025"]
    population_2030 = exported["population_2030"]
    built_now = np.clip(
        exported["built_surface_2025_m2"] / (CELL_SIZE_M**2), 0.0, 1.0
    )
    built_2030 = np.clip(
        exported["built_surface_2030_m2"] / (CELL_SIZE_M**2), 0.0, 1.0
    )
    built_change, pop_percentile, settlement_percentile = migration_components(
        population_2025, population_2030, built_now, built_2030
    )
    heat = exported["surface_temp_c"]
    arrays = {
        "population_2025": population_2025,
        "population_2030": population_2030,
        "population_growth_percentile": pop_percentile,
        "built_share_current": built_now,
        "built_change_pct": built_change,
        "settlement_growth_percentile": settlement_percentile,
        "green_share": np.clip(exported["green_share"], 0.0, 1.0),
        "built_bare_share": np.clip(exported["built_bare_share"], 0.0, 1.0),
        "surface_temp_c": heat,
        "heat_percentile": percentile_ranks(heat) / 100.0,
    }
    records = _cell_records(transform, arrays, versions, period)

    with connect() as conn:
        count = publish_metric_cells(conn, records)
        catalogue = (
            (
                "population", "2025", "European Commission GHSL P2023A",
                GHSL_POPULATION_ASSET, "population",
            ),
            (
                "population", "2030", "European Commission GHSL P2023A",
                GHSL_POPULATION_ASSET, "population",
            ),
            (
                "built_surface", "2025", "European Commission GHSL P2023A",
                GHSL_BUILT_SURFACE_ASSET, "settlement",
            ),
            (
                "built_surface", "2030", "European Commission GHSL P2023A",
                GHSL_BUILT_SURFACE_ASSET, "settlement",
            ),
            (
                "land_cover_fractions", "latest complete 12 months",
                "Google Dynamic World V1", DYNAMIC_WORLD_ASSET, "surface_heat",
            ),
            (
                "surface_temperature", period,
                "USGS Landsat Collection 2 Level-2",
                ",".join(LANDSAT_L2_ASSETS), "surface_heat",
            ),
        )
        for metric, epoch, source, source_url, layer in catalogue:
            register_analysis_raster(
                conn,
                metric=metric,
                epoch=epoch,
                source=source,
                source_url=source_url,
                path=stack_path,
                resolution_m=CELL_SIZE_M,
                licence="Open with source attribution",
                layer_version=versions[layer],
            )
        invalidated = 0
        for layer, source in (
            ("population", "European Commission GHSL P2023A via Earth Engine"),
            ("settlement", "European Commission GHSL P2023A via Earth Engine"),
            ("surface_heat", "USGS Landsat Collection 2 Level-2 via Earth Engine"),
        ):
            published, swept = bump_layer(conn, layer, source=source)
            if published != versions[layer]:
                raise RuntimeError(f"{layer} version changed during publication")
            invalidated += swept
    return {
        "status": "published",
        "cell_count": count,
        "layer_versions": versions,
        "data_period": period,
        "scores_invalidated": invalidated,
        "source_mode": "gee",
        "raster_path": str(stack_path),
    }


@app.task(name="aia_etl.tasks.environment.refresh_environmental_metrics")
def refresh_environmental_metrics(
    bbox: list[float] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Publish environmental and outlook inputs, preferring Earth Engine."""
    selected = (source or settings.environment_source).lower()
    if selected not in {"gee", "direct", "auto"}:
        raise ValueError("environment source must be gee, direct, or auto")
    if selected in {"gee", "auto"}:
        try:
            return _refresh_environmental_metrics_gee(bbox)
        except Exception:
            if selected == "gee":
                raise
            log.warning(
                "Earth Engine environmental refresh failed; using direct sources",
                exc_info=True,
            )
    return _refresh_environmental_metrics_direct(bbox)

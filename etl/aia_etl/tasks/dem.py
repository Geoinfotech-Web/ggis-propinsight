"""DEM & terrain derivatives (TDD §4.6, Phase 1 priority #2).

From a source DEM (Copernicus/SRTM, or a UAV DSM) compute slope, flow
accumulation, and the Topographic Wetness Index (TWI), write them as
Cloud-Optimised GeoTIFFs, and bump the `dem` layer.

    TWI = ln( a / tan(β) )
      a = upslope contributing area per unit contour length (flow accumulation)
      β = local slope angle (radians)

Geo libraries (rasterio, pysheds, rio-cogeo) are imported lazily so the module
loads without GDAL present (e.g. in the API image or a bare test runner).
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer, next_layer_version

log = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_SAMPLE_SPACING_M = 100.0


def _pixel_size_metres(
    x_res: float, y_res: float, *, geographic: bool, mid_lat: float = 0.0
) -> tuple[float, float]:
    """Approximate pixel width/height in metres for projected or lon/lat rasters."""
    if not geographic:
        return abs(x_res), abs(y_res)
    x_m = abs(x_res) * 111_320.0 * max(math.cos(math.radians(mid_lat)), 0.01)
    y_m = abs(y_res) * 110_574.0
    return x_m, y_m


def _sample_strides(
    x_res: float,
    y_res: float,
    *,
    geographic: bool,
    mid_lat: float,
    spacing_m: float = DEFAULT_SAMPLE_SPACING_M,
) -> tuple[int, int]:
    """Return row/column strides that keep DEM samples roughly ``spacing_m`` apart."""
    x_m, y_m = _pixel_size_metres(
        x_res, y_res, geographic=geographic, mid_lat=mid_lat
    )
    if x_m <= 0 or y_m <= 0 or spacing_m <= 0:
        raise ValueError("raster resolution and sample spacing must be positive")
    return max(1, round(spacing_m / y_m)), max(1, round(spacing_m / x_m))


def compute_slope_radians(dem_path: Path, out_path: Path) -> Path:
    """Slope angle (radians) via GDAL Horn method; written as a COG."""
    import numpy as np
    import rasterio
    from rasterio.io import MemoryFile

    with rasterio.open(dem_path) as src:
        dem = src.read(1, masked=True).astype("float32")
        px, py = src.res
        profile = src.profile
        mid_lat = (src.bounds.bottom + src.bounds.top) / 2
        geographic = bool(src.crs and src.crs.is_geographic)

    x_m, y_m = _pixel_size_metres(px, py, geographic=geographic, mid_lat=mid_lat)
    dzdy, dzdx = np.gradient(dem, y_m, x_m)
    slope = np.arctan(np.sqrt(dzdx**2 + dzdy**2)).astype("float32")

    profile.update(dtype="float32", count=1, compress="deflate")
    with MemoryFile() as mem:
        with mem.open(**profile) as tmp:
            tmp.write(slope.filled(0), 1)
        _to_cog(mem, out_path)
    return out_path


def compute_flow_accumulation(dem_path: Path, out_path: Path) -> Path:
    """D8 flow accumulation with pysheds (pit-filled), written as a COG."""
    import numpy as np
    import rasterio
    from pysheds.grid import Grid
    from rasterio.io import MemoryFile

    # pysheds 0.5 still calls NumPy's former ``in1d`` alias internally.
    if not hasattr(np, "in1d"):
        np.in1d = np.isin

    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))
    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)
    fdir = grid.flowdir(inflated)
    acc = grid.accumulation(fdir).astype("float32")

    with rasterio.open(dem_path) as src:
        profile = src.profile
    profile.update(dtype="float32", count=1, compress="deflate")
    with MemoryFile() as mem:
        with mem.open(**profile) as tmp:
            tmp.write(acc, 1)
        _to_cog(mem, out_path)
    return out_path


def compute_twi(
    slope_rad_path: Path, flow_acc_path: Path, out_path: Path, cell_size: float
) -> Path:
    """TWI = ln(a / tan(β)); a = accumulation * cell_size, guarded against zeros."""
    import numpy as np
    import rasterio
    from rasterio.io import MemoryFile

    with rasterio.open(slope_rad_path) as s, rasterio.open(flow_acc_path) as f:
        slope = s.read(1).astype("float32")
        acc = f.read(1).astype("float32")
        profile = s.profile

    tan_b = np.tan(np.maximum(slope, 1e-4))       # avoid div-by-zero on flats
    a = (acc + 1.0) * cell_size                    # +1 so log is defined everywhere
    twi = np.log(a / tan_b).astype("float32")

    profile.update(dtype="float32", count=1, compress="deflate")
    with MemoryFile() as mem:
        with mem.open(**profile) as tmp:
            tmp.write(twi, 1)
        _to_cog(mem, out_path)
    return out_path


def _to_cog(memfile: Any, out_path: Path) -> None:
    from rio_cogeo.cogeo import cog_translate
    from rio_cogeo.profiles import cog_profiles

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with memfile.open() as src:
        cog_translate(src, str(out_path), cog_profiles.get("deflate"), in_memory=True, quiet=True)


def sample_dem_derivatives(
    dem_path: Path,
    slope_rad_path: Path,
    twi_path: Path,
    flow_acc_path: Path | None = None,
    spacing_m: float = DEFAULT_SAMPLE_SPACING_M,
) -> list[dict[str, float]]:
    """Sample aligned terrain rasters into point records consumed by the API."""
    import numpy as np
    import rasterio
    from rasterio.transform import xy
    from rasterio.warp import transform

    with (
        rasterio.open(dem_path) as dem_src,
        rasterio.open(slope_rad_path) as slope_src,
        rasterio.open(twi_path) as twi_src,
    ):
        if dem_src.crs is None:
            raise ValueError("DEM has no CRS")
        if (
            slope_src.shape != dem_src.shape
            or twi_src.shape != dem_src.shape
            or slope_src.transform != dem_src.transform
            or twi_src.transform != dem_src.transform
        ):
            raise ValueError("DEM derivative rasters are not aligned")

        mid_lat = (dem_src.bounds.bottom + dem_src.bounds.top) / 2
        row_stride, col_stride = _sample_strides(
            *dem_src.res,
            geographic=dem_src.crs.is_geographic,
            mid_lat=mid_lat,
            spacing_m=spacing_m,
        )
        rows = np.arange(0, dem_src.height, row_stride)
        cols = np.arange(0, dem_src.width, col_stride)
        row_grid, col_grid = np.meshgrid(rows, cols, indexing="ij")

        dem = dem_src.read(1, masked=True)[::row_stride, ::col_stride]
        slope = slope_src.read(1, masked=True)[::row_stride, ::col_stride]
        twi = twi_src.read(1, masked=True)[::row_stride, ::col_stride]
        mask = np.ma.getmaskarray(dem) | np.ma.getmaskarray(slope) | np.ma.getmaskarray(twi)
        valid = ~mask & np.isfinite(dem) & np.isfinite(slope) & np.isfinite(twi)

        xs, ys = xy(dem_src.transform, row_grid[valid], col_grid[valid], offset="center")
        lons, lats = transform(dem_src.crs, "EPSG:4326", xs, ys)
        elevations = np.asarray(dem)[valid]
        slopes_deg = np.degrees(np.asarray(slope)[valid])
        twis = np.asarray(twi)[valid]
        flow_values = None
        if flow_acc_path is not None:
            with rasterio.open(flow_acc_path) as flow_src:
                if flow_src.shape != dem_src.shape or flow_src.transform != dem_src.transform:
                    raise ValueError("flow accumulation raster is not aligned")
                flow = flow_src.read(1, masked=True)[::row_stride, ::col_stride]
                flow_values = np.asarray(flow)[valid]
        pixel_x_m, pixel_y_m = _pixel_size_metres(
            *dem_src.res,
            geographic=dem_src.crs.is_geographic,
            mid_lat=mid_lat,
        )
        pixel_area_km2 = pixel_x_m * pixel_y_m / 1_000_000.0

    samples = [
        {
            "lon": float(lon),
            "lat": float(lat),
            "elevation_m": float(elevation),
            "slope_deg": float(slope_deg),
            "twi": float(twi_value),
            "flow_accumulation": (
                None if flow_values is None else float(flow_values[index])
            ),
            "contributing_area_km2": (
                None if flow_values is None else float(flow_values[index] * pixel_area_km2)
            ),
        }
        for index, (lon, lat, elevation, slope_deg, twi_value) in enumerate(
            zip(lons, lats, elevations, slopes_deg, twis, strict=True)
        )
    ]
    return samples


def publish_dem_samples(
    conn: Connection, samples: list[dict[str, Any]], layer_version: str
) -> int:
    """Replace API-facing DEM samples inside the caller's publish transaction."""
    if not samples:
        raise ValueError("terrain derivatives produced no valid DEM samples")
    conn.execute(text("DELETE FROM dem_samples"))
    conn.execute(
        text("SELECT setval(pg_get_serial_sequence('dem_samples', 'id'), 1, false)")
    )
    statement = text(
        """
        INSERT INTO dem_samples
          (geom, elevation_m, slope_deg, twi, flow_accumulation,
           contributing_area_km2, layer_version)
        VALUES
          (ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
           :elevation_m, :slope_deg, :twi, :flow_accumulation,
           :contributing_area_km2, :layer_version)
        """
    )
    # FCT at 100 m produces hundreds of thousands of records. Bounded batches
    # avoid constructing a second full-size parameter list in memory.
    for start in range(0, len(samples), 5_000):
        conn.execute(
            statement,
            [
                {**sample, "layer_version": layer_version}
                for sample in samples[start : start + 5_000]
            ],
        )
    return len(samples)


@app.task(name="aia_etl.tasks.dem.dem_from_gee")
def dem_from_gee(bbox: list[float] | None = None, scale: int = 30) -> dict[str, Any]:
    """Source the AOI DEM from Google Earth Engine (Copernicus GLO-30), then run
    the terrain derivatives. Defaults to the FCT pilot bbox.
    """
    from aia_etl.gee import export_dem_cop30
    from aia_etl.qa import FCT_BBOX

    aoi = tuple(bbox) if bbox else FCT_BBOX
    dem_out = Path(settings.data_dir) / "dem" / "cop30.tif"
    export_dem_cop30(aoi, dem_out, scale=scale)  # type: ignore[arg-type]
    source = "Google Earth Engine COPERNICUS/DEM/GLO30_2024_1"
    result = terrain_derivatives(str(dem_out), source=source)
    result["source"] = source
    result["aoi_bbox"] = list(aoi)
    return result


@app.task(name="aia_etl.tasks.dem.dem_from_copernicus")
def dem_from_copernicus(bbox: list[float] | None = None) -> dict[str, Any]:
    """Download Copernicus GLO-30 from the official Data Space STAC catalogue."""
    from aia_etl.qa import FCT_BBOX
    from aia_etl.sources.rasters import (
        download_file,
        merge_rasters,
        public_copernicus_dem_href,
        select_asset,
        stac_items,
    )

    aoi = tuple(bbox) if bbox else FCT_BBOX
    items = stac_items(
        settings.copernicus_stac_url,
        collection=settings.copernicus_dem_collection,
        bbox=aoi,
    )
    if not items:
        raise RuntimeError("Copernicus Data Space returned no GLO-30 tiles for the FCT")
    tile_dir = Path(settings.data_dir) / "dem" / "source"
    paths = [
        download_file(
            public_copernicus_dem_href(
                select_asset(item, ("data", "dem", "download"))
            ),
            tile_dir / f"{item['id']}.tif",
        )
        for item in items
    ]
    dem_out = merge_rasters(
        paths,
        Path(settings.data_dir) / "dem" / "cop30.tif",
        bounds=aoi,
    )
    result = terrain_derivatives(str(dem_out))
    result.update(
        source="Copernicus Data Space COP-DEM GLO-30",
        source_url=settings.copernicus_stac_url,
        aoi_bbox=list(aoi),
    )
    return result


@app.task(name="aia_etl.tasks.dem.terrain_derivatives")
def terrain_derivatives(
    dem_path: str,
    source: str = "Copernicus Data Space COP-DEM GLO-30",
) -> dict[str, Any]:
    """Produce terrain COGs, publish API samples, then atomically bump ``dem``."""
    import rasterio

    data = Path(settings.data_dir) / "dem"
    dem = Path(dem_path)
    with rasterio.open(dem) as src:
        mid_lat = (src.bounds.bottom + src.bounds.top) / 2
        x_m, y_m = _pixel_size_metres(
            *src.res,
            geographic=bool(src.crs and src.crs.is_geographic),
            mid_lat=mid_lat,
        )
        cell_size = (x_m + y_m) / 2

    slope = compute_slope_radians(dem, data / "slope.tif")
    acc = compute_flow_accumulation(dem, data / "flow_accumulation.tif")
    twi = compute_twi(slope, acc, data / "twi.tif", cell_size)
    samples = sample_dem_derivatives(dem, slope, twi, acc)

    with connect() as conn:
        version = next_layer_version(conn, "dem")
        published_samples = publish_dem_samples(conn, samples, version)
        bumped_version, invalidated = bump_layer(conn, "dem", source=source)
        if bumped_version != version:
            raise RuntimeError("DEM layer version changed during publication")

    summary = {
        "dem_version": version,
        "outputs": {"slope": str(slope), "flow_accumulation": str(acc), "twi": str(twi)},
        "published_samples": published_samples,
        "sample_spacing_m": DEFAULT_SAMPLE_SPACING_M,
        "scores_invalidated": invalidated,
    }
    log.info("terrain_derivatives complete: %s", summary)
    return summary

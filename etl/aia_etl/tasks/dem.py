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
from pathlib import Path
from typing import Any

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer

log = logging.getLogger(__name__)
settings = get_settings()


def compute_slope_radians(dem_path: Path, out_path: Path) -> Path:
    """Slope angle (radians) via GDAL Horn method; written as a COG."""
    import numpy as np
    import rasterio
    from rasterio.io import MemoryFile

    with rasterio.open(dem_path) as src:
        dem = src.read(1, masked=True).astype("float32")
        px, py = src.res
        profile = src.profile

    dzdx, dzdy = np.gradient(dem, px, py)
    slope = np.arctan(np.sqrt(dzdx**2 + dzdy**2)).astype("float32")

    profile.update(dtype="float32", count=1, compress="deflate")
    with MemoryFile() as mem:
        with mem.open(**profile) as tmp:
            tmp.write(slope.filled(0), 1)
        _to_cog(mem, out_path)
    return out_path


def compute_flow_accumulation(dem_path: Path, out_path: Path) -> Path:
    """D8 flow accumulation with pysheds (pit-filled), written as a COG."""
    import rasterio
    from pysheds.grid import Grid
    from rasterio.io import MemoryFile

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
    result = terrain_derivatives(str(dem_out))
    result["source"] = "GEE COPERNICUS/DEM/GLO30"
    result["aoi_bbox"] = list(aoi)
    return result


@app.task(name="aia_etl.tasks.dem.terrain_derivatives")
def terrain_derivatives(dem_path: str) -> dict[str, Any]:
    """Produce slope/flow-accumulation/TWI COGs from a source DEM and bump `dem`."""
    import rasterio

    data = Path(settings.data_dir) / "dem"
    dem = Path(dem_path)
    with rasterio.open(dem) as src:
        cell_size = abs(src.res[0])

    slope = compute_slope_radians(dem, data / "slope.tif")
    acc = compute_flow_accumulation(dem, data / "flow_accumulation.tif")
    twi = compute_twi(slope, acc, data / "twi.tif", cell_size)

    with connect() as conn:
        version, invalidated = bump_layer(conn, "dem", source="Copernicus/SRTM DEM")

    summary = {
        "dem_version": version,
        "outputs": {"slope": str(slope), "flow_accumulation": str(acc), "twi": str(twi)},
        "scores_invalidated": invalidated,
    }
    log.info("terrain_derivatives complete: %s", summary)
    return summary

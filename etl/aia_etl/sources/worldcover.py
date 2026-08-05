"""Wall-to-wall observed land-cover raster helpers."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

SOURCE_NAME = "ESA WorldCover 2021 v200"
SOURCE_URL = "https://worldcover2021.esa.int/download"
TILE_ROOT = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"

WORLD_COVER_CLASSES: dict[int, dict[str, str]] = {
    10: {"key": "tree_cover", "label": "Tree cover", "color": "#006400"},
    20: {"key": "shrubland", "label": "Shrubland", "color": "#ffbb22"},
    30: {"key": "grassland", "label": "Grassland", "color": "#ffff4c"},
    40: {"key": "cropland", "label": "Cropland", "color": "#f096ff"},
    50: {"key": "built_up", "label": "Built-up", "color": "#fa0000"},
    60: {"key": "bare_sparse", "label": "Bare / sparse vegetation", "color": "#b4b4b4"},
    70: {"key": "snow_ice", "label": "Snow / ice", "color": "#f0f0f0"},
    80: {"key": "water", "label": "Permanent water", "color": "#0064c8"},
    90: {"key": "wetland", "label": "Herbaceous wetland", "color": "#0096a0"},
    95: {"key": "mangroves", "label": "Mangroves", "color": "#00cf75"},
    100: {"key": "moss_lichen", "label": "Moss / lichen", "color": "#fae6a0"},
}

DYNAMIC_WORLD_CLASSES: dict[int, dict[str, str]] = {
    0: {"key": "water", "label": "Water", "color": "#419bdf"},
    1: {"key": "trees", "label": "Trees", "color": "#397d49"},
    2: {"key": "grass", "label": "Grass", "color": "#88b053"},
    3: {"key": "flooded_vegetation", "label": "Flooded vegetation", "color": "#7a87c6"},
    4: {"key": "crops", "label": "Crops", "color": "#e49635"},
    5: {"key": "shrub_scrub", "label": "Shrub / scrub", "color": "#dfc35a"},
    6: {"key": "built_area", "label": "Built area", "color": "#c4281b"},
    7: {"key": "bare_ground", "label": "Bare ground", "color": "#a59b8f"},
    8: {"key": "snow_ice", "label": "Snow / ice", "color": "#b39fe1"},
}


def worldcover_tile_urls(bounds: tuple[float, float, float, float]) -> list[str]:
    """Return the 3-degree WorldCover tiles intersecting ``bounds``."""
    min_lon, min_lat, max_lon, max_lat = bounds
    lon_starts = range(math.floor(min_lon / 3) * 3, math.ceil(max_lon / 3) * 3, 3)
    lat_starts = range(math.floor(min_lat / 3) * 3, math.ceil(max_lat / 3) * 3, 3)
    urls: list[str] = []
    for lat in lat_starts:
        for lon in lon_starts:
            lat_code = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
            lon_code = f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"
            name = f"ESA_WorldCover_10m_2021_v200_{lat_code}{lon_code}_Map.tif"
            urls.append(f"{TILE_ROOT}/{name}")
    return urls


def write_clipped_cog(
    sources: list[str | Path],
    bounds: tuple[float, float, float, float],
    geometries: list[dict[str, Any]],
    out_path: Path,
) -> Path:
    """Mosaic only needed COG windows, mask to FCT, and publish a local COG."""
    import numpy as np
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.io import MemoryFile
    from rasterio.merge import merge
    from rio_cogeo.cogeo import cog_translate
    from rio_cogeo.profiles import cog_profiles

    out_path.parent.mkdir(parents=True, exist_ok=True)
    env_options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    }
    with rasterio.Env(**env_options):
        datasets = [rasterio.open(str(source)) for source in sources]
        try:
            mosaic, transform = merge(datasets, bounds=bounds, nodata=255)
        finally:
            for dataset in datasets:
                dataset.close()

    inside = geometry_mask(
        geometries,
        out_shape=mosaic.shape[1:],
        transform=transform,
        invert=True,
    )
    mosaic[0] = np.where(inside, mosaic[0], 255).astype("uint8")
    profile = {
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": 255,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
    }
    with MemoryFile() as mem:
        with mem.open(**profile) as dst:
            dst.write(mosaic)
        with mem.open() as src:
            cog_translate(
                src,
                str(out_path),
                cog_profiles.get("deflate"),
                in_memory=True,
                quiet=True,
            )
    return out_path


def export_worldcover(
    bounds: tuple[float, float, float, float],
    geometries: list[dict[str, Any]],
    out_path: Path,
) -> Path:
    return write_clipped_cog(worldcover_tile_urls(bounds), bounds, geometries, out_path)

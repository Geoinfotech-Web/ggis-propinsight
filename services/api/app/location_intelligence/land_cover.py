"""Point sampling and map tiles for wall-to-wall observed land cover."""
from __future__ import annotations

import asyncio
import io
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from fastapi import HTTPException, Response
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject, transform
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ADVISORY = (
    "Satellite-derived observed land cover, not statutory zoning, allocation, title, "
    "or development permission. Verify planned use with AGIS/FCTA."
)


async def _current_raster(session: AsyncSession) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT r.raster_path, r.source, r.source_url, r.period_start, r.period_end,
                   r.resolution_m, r.classes, r.layer_version
            FROM land_cover_rasters r
            JOIN layer_registry registry
              ON registry.layer = 'land_cover' AND registry.version = r.layer_version
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT 1
            """
        )
    )
    row = result.mappings().first()
    if not row:
        return None
    payload = dict(row)
    if isinstance(payload["classes"], str):
        payload["classes"] = json.loads(payload["classes"])
    return payload


def _class_info(raster: dict[str, Any], value: int) -> dict[str, Any] | None:
    info = raster["classes"].get(str(value)) or raster["classes"].get(value)
    if not info:
        return None
    return {
        "class_value": value,
        "category": info["key"],
        "label": info["label"],
        "designation": "observed_land_cover",
        "source": raster["source"],
        "source_url": raster["source_url"],
        "period_start": raster["period_start"].isoformat() if raster["period_start"] else None,
        "period_end": raster["period_end"].isoformat() if raster["period_end"] else None,
        "resolution_m": raster["resolution_m"],
        "advisory": ADVISORY,
    }


def _sample(path: str, lon: float, lat: float) -> int | None:
    if not Path(path).is_file():
        return None
    with rasterio.open(path) as src:
        xs, ys = [lon], [lat]
        if src.crs and src.crs.to_epsg() != 4326:
            xs, ys = transform("EPSG:4326", src.crs, xs, ys)
        value = int(next(src.sample([(xs[0], ys[0])]))[0])
        if value == src.nodata:
            return None
        return value


async def land_cover_at_point(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, Any] | None:
    raster = await _current_raster(session)
    if not raster:
        return None
    value = await asyncio.to_thread(_sample, raster["raster_path"], lon, lat)
    return _class_info(raster, value) if value is not None else None


def _tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    half = 20037508.342789244
    span = (half * 2) / (2**z)
    left = -half + x * span
    right = left + span
    top = half - y * span
    return left, top - span, right, top


def _render_tile(path: str, classes: dict[str, Any], z: int, x: int, y: int) -> bytes:
    data = np.full((256, 256), 255, dtype="uint8")
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=data,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=from_bounds(*_tile_bounds(z, x, y), 256, 256),
            dst_crs="EPSG:3857",
            dst_nodata=255,
            resampling=Resampling.nearest,
        )
    rgba = np.zeros((256, 256, 4), dtype="uint8")
    for raw_value, info in classes.items():
        value = int(raw_value)
        color = str(info["color"]).lstrip("#")
        rgb = tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))
        rgba[data == value] = (*rgb, 185)
    output = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(output, format="PNG", compress_level=3)
    return output.getvalue()


@lru_cache(maxsize=512)
def _render_tile_cached(
    path: str,
    classes_json: str,
    layer_version: str,
    z: int,
    x: int,
    y: int,
) -> bytes:
    """Cache rendered tiles; the version key invalidates them after an ETL publish."""
    del layer_version
    return _render_tile(path, json.loads(classes_json), z, x, y)


async def land_cover_tile(
    session: AsyncSession, z: int, x: int, y: int
) -> Response:
    if z < 0 or z > 18 or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
        raise HTTPException(status_code=404, detail="tile outside valid range")
    raster = await _current_raster(session)
    if not raster or not Path(raster["raster_path"]).is_file():
        raise HTTPException(status_code=404, detail="land-cover raster is unpublished")
    content = await asyncio.to_thread(
        _render_tile_cached,
        raster["raster_path"],
        json.dumps(raster["classes"], sort_keys=True, separators=(",", ":")),
        str(raster["layer_version"]),
        z,
        x,
        y,
    )
    return Response(
        content=content,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Layer-Version": raster["layer_version"],
        },
    )


async def land_cover_meta(session: AsyncSession) -> dict[str, Any]:
    raster = await _current_raster(session)
    if not raster:
        return {"status": "unpublished", "advisory": ADVISORY}
    return {
        "status": "published",
        "version": raster["layer_version"],
        "source": raster["source"],
        "source_url": raster["source_url"],
        "period_start": raster["period_start"],
        "period_end": raster["period_end"],
        "resolution_m": raster["resolution_m"],
        "classes": raster["classes"],
        "advisory": ADVISORY,
    }

"""Shared direct-download and STAC helpers for authoritative raster sources."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx

COPERNICUS_DEM_S3_PREFIX = "s3://eodata/auxdata/CopDEM_COG/copernicus-dem-30m/"


def public_copernicus_dem_href(href: str) -> str:
    """Translate CDSE's authenticated S3 reference to the public AWS GLO-30 COG."""
    if not href.startswith(COPERNICUS_DEM_S3_PREFIX):
        return href
    relative = href.removeprefix(COPERNICUS_DEM_S3_PREFIX)
    if ".." in Path(relative).parts or not relative.lower().endswith(".tif"):
        raise ValueError("invalid Copernicus DEM asset path")
    return f"https://copernicus-dem-30m.s3.amazonaws.com/{relative}"


def signed_planetary_computer_href(href: str, sign_url: str) -> str:
    """Return a short-lived, read-only URL for a Planetary Computer COG asset."""
    if ".blob.core.windows.net/" not in href:
        return href
    response = httpx.get(sign_url, params={"href": href}, timeout=30.0)
    response.raise_for_status()
    signed = response.json().get("href")
    if not isinstance(signed, str) or not signed.startswith("https://"):
        raise RuntimeError("Planetary Computer signing response has no HTTPS asset URL")
    return signed


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path, *, timeout_s: float = 180.0) -> Path:
    """Download atomically so a failed provider never leaves a publishable partial file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    partial.unlink(missing_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=timeout_s) as response:
        response.raise_for_status()
        with partial.open("wb") as stream:
            for chunk in response.iter_bytes():
                stream.write(chunk)
    if not partial.is_file() or partial.stat().st_size == 0:
        raise RuntimeError(f"provider returned an empty file for {url}")
    partial.replace(destination)
    return destination


def stac_items(
    stac_url: str,
    *,
    collection: str,
    bbox: Iterable[float],
    datetime_range: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "collections": [collection],
        "bbox": list(bbox),
        "limit": limit,
    }
    if datetime_range:
        payload["datetime"] = datetime_range
    response = httpx.post(
        f"{stac_url.rstrip('/')}/search",
        json=payload,
        follow_redirects=True,
        timeout=60.0,
    )
    response.raise_for_status()
    body = response.json()
    features = body.get("features") if isinstance(body, dict) else None
    if not isinstance(features, list):
        raise RuntimeError("STAC response does not contain a feature list")
    return features


def select_asset(item: dict[str, Any], candidates: Iterable[str]) -> str:
    assets = item.get("assets") or {}
    for key in candidates:
        asset = assets.get(key)
        href = asset.get("href") if isinstance(asset, dict) else None
        if isinstance(href, str) and href:
            return href
    available = ", ".join(sorted(assets))
    raise RuntimeError(f"none of the requested STAC assets exists; available: {available}")


def merge_rasters(
    paths: list[Path],
    destination: Path,
    *,
    bounds: tuple[float, float, float, float] | None = None,
) -> Path:
    """Merge source tiles into a compressed GeoTIFF; callers derive final COGs."""
    import rasterio
    from rasterio.merge import merge

    if not paths:
        raise ValueError("at least one raster is required")
    sources = [rasterio.open(path) for path in paths]
    try:
        data, transform = merge(sources, bounds=bounds)
        profile = sources[0].profile.copy()
        profile.update(
            height=data.shape[1],
            width=data.shape[2],
            transform=transform,
            count=data.shape[0],
            compress="deflate",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(".partial.tif")
        partial.unlink(missing_ok=True)
        with rasterio.open(partial, "w", **profile) as output:
            output.write(data)
        partial.replace(destination)
    finally:
        for source in sources:
            source.close()
    return destination

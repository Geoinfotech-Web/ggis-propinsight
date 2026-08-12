"""Vectorise observed tree-cover pixels into analytical canopy zones."""
from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def tree_class_values(classes: dict[int, dict[str, str]]) -> set[int]:
    return {
        int(value)
        for value, metadata in classes.items()
        if metadata.get("key") in {"tree_cover", "trees"}
    }


def minimum_canopy_pixels(resolution_m: int, minimum_area_ha: float = 0.25) -> int:
    if resolution_m <= 0:
        raise ValueError("resolution_m must be positive")
    return max(1, math.ceil(minimum_area_ha * 10_000 / resolution_m**2))


def canopy_geometries(
    raster_path: Path,
    classes: dict[int, dict[str, str]],
    resolution_m: int = 10,
) -> Iterator[dict[str, Any]]:
    """Return connected tree-cover patches in WGS84 after a pixel-size area sieve."""
    import numpy as np
    import rasterio
    from rasterio.features import shapes, sieve
    from rasterio.warp import transform_geom
    from shapely import make_valid
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    values = tree_class_values(classes)
    if not values:
        return
    with rasterio.open(raster_path) as dataset:
        band = dataset.read(1)
        mask = np.isin(band, list(values))
        if not mask.any():
            return
        mask = sieve(
            mask.astype("uint8"),
            size=minimum_canopy_pixels(resolution_m),
            connectivity=8,
        ).astype(bool)
        source_crs = dataset.crs or "EPSG:4326"
        for geometry, _value in shapes(
            mask.astype("uint8"), mask=mask, transform=dataset.transform, connectivity=8
        ):
            wgs84 = transform_geom(source_crs, "EPSG:4326", geometry, precision=7)
            simplified = shape(wgs84).simplify(0.00005, preserve_topology=False)
            if not simplified.is_valid:
                simplified = make_valid(simplified)
            if simplified.geom_type == "GeometryCollection":
                simplified = unary_union(
                    [
                        part
                        for part in simplified.geoms
                        if part.geom_type in {"Polygon", "MultiPolygon"}
                    ]
                )
            if not simplified.is_empty and simplified.geom_type in {"Polygon", "MultiPolygon"}:
                yield mapping(simplified)

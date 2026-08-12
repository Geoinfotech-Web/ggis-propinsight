"""Bounded visual-evidence layers for the professional Cesium view."""
from __future__ import annotations

import json
import math
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BUILDING_ADVISORY = (
    "Analytical Overture footprints. Heights are published, floor-derived, or a "
    "clearly marked 6 m visual default; they are not a building survey."
)
VEGETATION_ADVISORY = (
    "Satellite-observed tree-cover zones of at least 0.25 ha. Canopy height is "
    "illustrative; polygons are not individual surveyed trees or ecological clearance."
)
MAX_CONTEXT_RADIUS_M = 3_000


def validate_context_bbox(
    bbox: tuple[float, float, float, float], center: tuple[float, float]
) -> None:
    min_lon, min_lat, max_lon, max_lat = bbox
    lon, lat = center
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status_code=422, detail="bbox minimums must be below maximums")
    if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
        raise HTTPException(status_code=422, detail="selected point must be inside bbox")
    lat_scale = 111_320.0
    lon_scale = lat_scale * math.cos(math.radians(lat))
    half_width = max(abs(lon - min_lon), abs(max_lon - lon)) * lon_scale
    half_height = max(abs(lat - min_lat), abs(max_lat - lat)) * lat_scale
    if half_width > 3_150 or half_height > 3_150:
        raise HTTPException(
            status_code=422,
            detail="professional 3D bbox cannot exceed the nearest 3 km site context",
        )


async def _version(session: AsyncSession, layer: str) -> str | None:
    result = await session.execute(
        text("SELECT version FROM layer_registry WHERE layer = :layer"), {"layer": layer}
    )
    value = result.scalar()
    return str(value) if value else None


def _empty(version: str | None, advisory: str) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "status": "unpublished" if version in {None, "unpublished"} else "published",
            "version": version,
            "total_count": 0,
            "feature_count": 0,
            "truncated": False,
            "advisory": advisory,
        },
    }


async def building_feature_collection(
    session: AsyncSession,
    bbox: tuple[float, float, float, float],
    center: tuple[float, float],
    *,
    limit: int = 10_000,
) -> dict[str, Any]:
    validate_context_bbox(bbox, center)
    version = await _version(session, "buildings_3d")
    if version in {None, "unpublished"}:
        return _empty(version, BUILDING_ADVISORY)
    min_lon, min_lat, max_lon, max_lat = bbox
    lon, lat = center
    params = {
        "min_lon": min_lon,
        "min_lat": min_lat,
        "max_lon": max_lon,
        "max_lat": max_lat,
        "lon": lon,
        "lat": lat,
        "limit": limit,
    }
    count = int(
        (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM building_footprints
                    WHERE geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                    """
                ),
                params,
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            text(
                """
                SELECT source_id, parent_source_id, feature_type, building_class,
                       height_m, num_floors, min_height_m, display_height_m,
                       height_basis, source_datasets, release,
                       ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.000002), 7) AS geometry
                FROM building_footprints
                WHERE geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), id
                LIMIT :limit
                """
            ),
            params,
        )
    ).all()
    features = [
        {
            "type": "Feature",
            "id": row.source_id,
            "geometry": json.loads(row.geometry),
            "properties": {
                "source_id": row.source_id,
                "parent_source_id": row.parent_source_id,
                "feature_type": row.feature_type,
                "building_class": row.building_class,
                "height_m": row.height_m,
                "num_floors": row.num_floors,
                "min_height_m": row.min_height_m,
                "display_height_m": row.display_height_m,
                "height_basis": row.height_basis,
                "source_datasets": row.source_datasets or [],
                "release": row.release,
            },
        }
        for row in rows
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "status": "published",
            "version": version,
            "source": "Overture Maps Buildings",
            "source_url": "https://docs.overturemaps.org/guides/buildings/",
            "release": features[0]["properties"]["release"] if features else None,
            "total_count": count,
            "feature_count": len(features),
            "truncated": count > len(features),
            "advisory": BUILDING_ADVISORY,
        },
    }


async def vegetation_feature_collection(
    session: AsyncSession,
    bbox: tuple[float, float, float, float],
    center: tuple[float, float],
    *,
    limit: int = 3_000,
) -> dict[str, Any]:
    validate_context_bbox(bbox, center)
    version = await _version(session, "vegetation_3d")
    if version in {None, "unpublished"}:
        return _empty(version, VEGETATION_ADVISORY)
    min_lon, min_lat, max_lon, max_lat = bbox
    lon, lat = center
    params = {
        "min_lon": min_lon,
        "min_lat": min_lat,
        "max_lon": max_lon,
        "max_lat": max_lat,
        "lon": lon,
        "lat": lat,
        "limit": limit,
    }
    count = int(
        (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM vegetation_canopy_areas
                    WHERE geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                    """
                ),
                params,
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            text(
                """
                SELECT id, source, source_url, period_start, period_end,
                       resolution_m, area_ha,
                       ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.00001), 7) AS geometry
                FROM vegetation_canopy_areas
                WHERE geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                ORDER BY area_ha DESC, id
                LIMIT :limit
                """
            ),
            params,
        )
    ).all()
    features = [
        {
            "type": "Feature",
            "id": str(row.id),
            "geometry": json.loads(row.geometry),
            "properties": {
                "source": row.source,
                "source_url": row.source_url,
                "period_start": row.period_start.isoformat() if row.period_start else None,
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "resolution_m": row.resolution_m,
                "area_ha": row.area_ha,
                "display_height_m": 4,
                "height_basis": "illustrative_canopy",
            },
        }
        for row in rows
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "status": "published",
            "version": version,
            "source": features[0]["properties"]["source"] if features else None,
            "source_url": features[0]["properties"]["source_url"] if features else None,
            "period_start": features[0]["properties"]["period_start"] if features else None,
            "period_end": features[0]["properties"]["period_end"] if features else None,
            "resolution_m": features[0]["properties"]["resolution_m"] if features else None,
            "total_count": count,
            "feature_count": len(features),
            "truncated": count > len(features),
            "advisory": VEGETATION_ADVISORY,
        },
    }

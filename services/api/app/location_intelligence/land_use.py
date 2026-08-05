"""Read open land-use context without representing it as statutory zoning."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LAND_USE_LABELS: dict[str, str] = {
    "residential": "Residential",
    "industrial": "Industrial",
    "commercial": "Commercial / retail",
    "institutional": "Institutional / public service",
    "protected_reserve": "Protected / reserve",
    "recreation_open_space": "Recreation / open space",
    "agricultural": "Agricultural",
    "military_restricted": "Military / restricted",
    "transportation": "Transportation",
    "construction_development": "Construction / development",
    "extractive": "Extractive / quarry",
    "landfill": "Landfill",
    "cemetery": "Cemetery",
    "other": "Other mapped use",
}

REFERENCE_ADVISORY = (
    "Open mapped land-use context only; not a legal zoning, allocation, title, "
    "or development-control confirmation. Verify with AGIS/FCTA."
)
OFFICIAL_ADVISORY = (
    "Official planning reference; confirm the current plan, plot allocation, title, "
    "and development permission directly with AGIS/FCTA."
)
ADVISORY = REFERENCE_ADVISORY


async def _is_published(session: AsyncSession) -> tuple[bool, str | None]:
    result = await session.execute(
        text("SELECT version FROM layer_registry WHERE layer = 'land_use'")
    )
    version = result.scalar()
    return bool(version and version != "unpublished"), str(version) if version else None


def _properties(row: Any) -> dict[str, Any]:
    return {
        "category": row.category,
        "label": LAND_USE_LABELS.get(row.category, row.category.replace("_", " ").title()),
        "name": row.name,
        "source_class": row.source_class,
        "source_subtype": row.source_subtype,
        "designation": row.designation,
        "source": row.source,
        "source_url": row.source_url,
        "effective_date": row.effective_date.isoformat() if row.effective_date else None,
        "advisory": (
            OFFICIAL_ADVISORY
            if row.designation == "official_masterplan"
            else REFERENCE_ADVISORY
        ),
    }


async def land_use_at_point(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, Any] | None:
    """Return the most specific mapped use covering a point."""
    published, _ = await _is_published(session)
    if not published:
        return None
    result = await session.execute(
        text(
            """
            SELECT category, name, source_class, source_subtype, designation,
                   source, source_url, effective_date
            FROM land_use_areas
            WHERE ST_Covers(
              geom,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            )
            ORDER BY
              CASE WHEN designation = 'official_masterplan' THEN 0 ELSE 1 END,
              ST_Area(geom::geography), id
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    )
    row = result.first()
    return _properties(row) if row else None


async def land_use_feature_collection(
    session: AsyncSession,
    bbox: tuple[float, float, float, float],
    *,
    limit: int = 5_000,
    tolerance: float = 0.00003,
) -> dict[str, Any]:
    """GeoJSON for a map viewport, with publication and advisory metadata."""
    published, version = await _is_published(session)
    if not published:
        return {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {"status": "unpublished", "version": version, "advisory": ADVISORY},
        }
    min_lon, min_lat, max_lon, max_lat = bbox
    result = await session.execute(
        text(
            """
            SELECT source_id, category, name, source_class, source_subtype,
                   designation, source, source_url, effective_date,
                   ST_AsGeoJSON(
                     ST_SimplifyPreserveTopology(geom, :tolerance), 6
                   ) AS geometry
            FROM land_use_areas
            WHERE geom && ST_MakeEnvelope(
              :min_lon, :min_lat, :max_lon, :max_lat, 4326
            )
            ORDER BY
              CASE WHEN designation = 'official_masterplan' THEN 1 ELSE 0 END,
              category, id
            LIMIT :limit
            """
        ),
        {
            "min_lon": min_lon,
            "min_lat": min_lat,
            "max_lon": max_lon,
            "max_lat": max_lat,
            "tolerance": tolerance,
            "limit": limit,
        },
    )
    features = [
        {
            "type": "Feature",
            "id": row.source_id,
            "geometry": json.loads(row.geometry),
            "properties": _properties(row),
        }
        for row in result
    ]
    designations = sorted(
        {feature["properties"]["designation"] for feature in features}
    )
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "status": "published",
            "version": version,
            "feature_count": len(features),
            "designations": designations,
            "advisory": ADVISORY,
        },
    }

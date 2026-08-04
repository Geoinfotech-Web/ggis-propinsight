"""Amenities domain scoring — PostGIS KNN distances × fct-v1 weights (TDD §4.4)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.engine import DomainScore, Indicator, linear_decay, score_domain

# Mirrors migration 0001 fct-v1 amenities weights.
AMENITY_WEIGHTS: dict[str, float] = {
    "school": 0.20,
    "hospital": 0.20,
    "water": 0.15,
    "power": 0.15,
    "isp": 0.10,
    "market": 0.10,
    "bank": 0.05,
    "fuel": 0.05,
}

# Categories shown as named lists / map markers within the scoring radius.
NEARBY_CATEGORIES: tuple[str, ...] = (
    "school",
    "hospital",
    "market",
    "bank",
    "power",
    "fuel",
)

# Full credit within 500 m; zero beyond 5 km (Phase 1 defaults).
D_MIN_M = 500.0
D_MAX_M = 5000.0


def score_amenities(
    nearest: dict[str, dict[str, Any] | None] | dict[str, float | None],
) -> DomainScore:
    """Aggregate nearest-amenity distances into a 0..100 domain score.

    ``nearest`` may be either legacy ``{category: distance_m}`` or
    ``{category: {"distance_m": float, "name": str | None}}``.
    """
    indicators: list[Indicator] = []
    for category, weight in AMENITY_WEIGHTS.items():
        info = nearest.get(category)
        if info is None:
            indicators.append(Indicator(key=category, value=None, weight=weight, raw=None))
            continue
        if isinstance(info, (int, float)):
            dist = float(info)
            name = None
        else:
            dist_raw = info.get("distance_m")
            if dist_raw is None:
                indicators.append(Indicator(key=category, value=None, weight=weight, raw=None))
                continue
            dist = float(dist_raw)
            name = info.get("name")
        raw: dict[str, Any] = {"distance_m": round(dist, 1)}
        if name:
            raw["name"] = name
        indicators.append(
            Indicator(
                key=category,
                value=linear_decay(dist, D_MIN_M, D_MAX_M),
                weight=weight,
                raw=raw,
            )
        )
    return score_domain(
        "amenities",
        indicators,
        confidence="Medium",
        note="Nearest POI distances (fct-v1 linear decay).",
    )


async def nearest_pois(
    session: AsyncSession, lon: float, lat: float, *, radius_m: float = D_MAX_M
) -> dict[str, dict[str, Any] | None]:
    """Nearest POI per amenity category within `radius_m` (PostGIS KNN + name).

    Capped by radius so a location with no nearby data reports "none" instead of
    surfacing an amenity tens of km away (which scores ~0 anyway).
    """
    categories = list(AMENITY_WEIGHTS.keys())
    result = await session.execute(
        text(
            """
            SELECT DISTINCT ON (category)
                   category,
                   name,
                   ST_Distance(
                     geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                   ) AS distance_m
            FROM poi
            WHERE category = ANY(:categories)
              AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
                  )
            ORDER BY category,
                     geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            """
        ),
        {"lon": lon, "lat": lat, "categories": categories, "radius_m": radius_m},
    )
    found: dict[str, dict[str, Any]] = {}
    for row in result:
        found[row.category] = {
            "distance_m": float(row.distance_m),
            "name": row.name,
        }
    return {cat: found.get(cat) for cat in categories}


async def nearest_poi_distances(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, float | None]:
    """Nearest distance (metres) per amenity category (compat wrapper)."""
    nearest = await nearest_pois(session, lon, lat)
    return {
        cat: (None if info is None else float(info["distance_m"]))
        for cat, info in nearest.items()
    }


async def pois_within_radius(
    session: AsyncSession,
    lon: float,
    lat: float,
    *,
    categories: tuple[str, ...] | list[str] = NEARBY_CATEGORIES,
    radius_m: float = D_MAX_M,
    limit_per_category: int = 12,
) -> list[dict[str, Any]]:
    """Named POIs within radius for map/scorecard lists (capped per category)."""
    result = await session.execute(
        text(
            """
            WITH ranked AS (
              SELECT
                category,
                COALESCE(NULLIF(TRIM(name), ''), INITCAP(category)) AS name,
                ST_Distance(
                  geom::geography,
                  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_m,
                ST_X(geom::geometry) AS lon,
                ST_Y(geom::geometry) AS lat,
                ROW_NUMBER() OVER (
                  PARTITION BY category
                  ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                ) AS rn
              FROM poi
              WHERE category = ANY(:categories)
                AND ST_DWithin(
                  geom::geography,
                  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                  :radius_m
                )
            )
            SELECT category, name, distance_m, lon, lat
            FROM ranked
            WHERE rn <= :limit_per_category
            ORDER BY category, distance_m
            """
        ),
        {
            "lon": lon,
            "lat": lat,
            "categories": list(categories),
            "radius_m": radius_m,
            "limit_per_category": limit_per_category,
        },
    )
    return [
        {
            "category": row.category,
            "name": row.name,
            "distance_m": round(float(row.distance_m), 1),
            "lon": float(row.lon),
            "lat": float(row.lat),
        }
        for row in result
    ]


def domainscore_evidence(ds: DomainScore) -> dict[str, Any]:
    return dict(ds.indicators)

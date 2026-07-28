"""Amenities domain scoring — PostGIS KNN distances × fct-v1 weights (TDD §4.4)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.engine import Indicator, DomainScore, linear_decay, score_domain

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

# Full credit within 500 m; zero beyond 5 km (Phase 1 defaults).
D_MIN_M = 500.0
D_MAX_M = 5000.0


def score_amenities(distances_m: dict[str, float | None]) -> DomainScore:
    """Aggregate nearest-amenity distances into a 0..100 domain score."""
    indicators: list[Indicator] = []
    for category, weight in AMENITY_WEIGHTS.items():
        dist = distances_m.get(category)
        if dist is None:
            indicators.append(Indicator(key=category, value=None, weight=weight, raw=None))
        else:
            indicators.append(
                Indicator(
                    key=category,
                    value=linear_decay(dist, D_MIN_M, D_MAX_M),
                    weight=weight,
                    raw={"distance_m": round(dist, 1)},
                )
            )
    return score_domain(
        "amenities",
        indicators,
        confidence="Medium",
        note="Nearest POI distances (fct-v1 linear decay).",
    )


async def nearest_poi_distances(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, float | None]:
    """Nearest distance (metres) per amenity category via PostGIS KNN."""
    categories = list(AMENITY_WEIGHTS.keys())
    result = await session.execute(
        text(
            """
            SELECT DISTINCT ON (category)
                   category,
                   ST_Distance(
                     geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                   ) AS distance_m
            FROM poi
            WHERE category = ANY(:categories)
            ORDER BY category,
                     geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            """
        ),
        {"lon": lon, "lat": lat, "categories": categories},
    )
    found = {row.category: float(row.distance_m) for row in result}
    return {cat: found.get(cat) for cat in categories}


def domainscore_evidence(ds: DomainScore) -> dict[str, Any]:
    return dict(ds.indicators)

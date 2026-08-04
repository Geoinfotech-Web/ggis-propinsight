"""Feasibility domain — DEM samples + flood + utility proximity (fct-v1)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.engine import DomainScore, Indicator, linear_decay, score_domain

WEIGHTS: dict[str, float] = {
    "slope": 0.30,
    "flood": 0.25,
    "utility_distance": 0.25,
    "catchment": 0.20,
}

# A terrain sample further than this from the click isn't representative — treat
# as no local DEM coverage rather than reporting a distant sample.
DEM_SAMPLE_MAX_M = 2000.0

# Flat ≤ 5°, unsuitable ≥ 25°.
SLOPE_GOOD = 5.0
SLOPE_BAD = 25.0
# Utility full credit ≤ 300 m, zero ≥ 3 km.
UTIL_D_MIN = 300.0
UTIL_D_MAX = 3000.0
# TWI: lower is better for buildability (less wetness). Cap score at TWI ≤ 5, zero ≥ 15.
TWI_GOOD = 5.0
TWI_BAD = 15.0


def _slope_score(slope_deg: float) -> float:
    return linear_decay(slope_deg, SLOPE_GOOD, SLOPE_BAD)


def _twi_score(twi: float) -> float:
    return linear_decay(twi, TWI_GOOD, TWI_BAD)


def score_feasibility(
    *,
    slope_deg: float | None,
    flood_normalised: float | None,
    utility_distance_m: float | None,
    twi: float | None,
) -> DomainScore:
    indicators = [
        Indicator(
            key="slope",
            value=None if slope_deg is None else _slope_score(slope_deg),
            weight=WEIGHTS["slope"],
            raw=None if slope_deg is None else {"slope_deg": round(slope_deg, 2)},
        ),
        Indicator(
            key="flood",
            value=flood_normalised,
            weight=WEIGHTS["flood"],
            raw=None if flood_normalised is None else {"flood_normalised": flood_normalised},
        ),
        Indicator(
            key="utility_distance",
            value=None
            if utility_distance_m is None
            else linear_decay(utility_distance_m, UTIL_D_MIN, UTIL_D_MAX),
            weight=WEIGHTS["utility_distance"],
            raw=None
            if utility_distance_m is None
            else {"distance_m": round(utility_distance_m, 1)},
        ),
        Indicator(
            key="catchment",
            value=None if twi is None else _twi_score(twi),
            weight=WEIGHTS["catchment"],
            raw=None if twi is None else {"twi": round(twi, 2)},
        ),
    ]
    return score_domain(
        "feasibility",
        indicators,
        confidence="Medium",
        note="DEM sample + flood + nearest water/power utility (fct-v1).",
    )


async def nearest_dem_sample(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, float] | None:
    exists = await session.execute(
        text("SELECT to_regclass('public.dem_samples') IS NOT NULL AS ok")
    )
    if not bool(exists.scalar()):
        return None
    result = await session.execute(
        text(
            """
            SELECT slope_deg, twi, elevation_m,
                   ST_Distance(
                     geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                   ) AS distance_m
            FROM dem_samples
            WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
                  )
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat, "radius_m": DEM_SAMPLE_MAX_M},
    )
    row = result.first()
    if row is None:
        return None
    return {
        "slope_deg": float(row.slope_deg),
        "twi": float(row.twi),
        "elevation_m": float(row.elevation_m),
        "distance_m": float(row.distance_m),
    }


async def nearest_utility_distance_m(
    session: AsyncSession, lon: float, lat: float
) -> float | None:
    """Nearest water or power POI (utility connectivity proxy)."""
    exists = await session.execute(
        text("SELECT to_regclass('public.poi') IS NOT NULL AS ok")
    )
    if not bool(exists.scalar()):
        return None
    result = await session.execute(
        text(
            """
            SELECT ST_Distance(
                     geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                   ) AS distance_m
            FROM poi
            WHERE category IN ('water', 'power')
              AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
                  )
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat, "radius_m": UTIL_D_MAX},
    )
    row = result.first()
    return float(row.distance_m) if row else None

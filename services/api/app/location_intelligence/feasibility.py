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
SITE_CONTEXT_RADIUS_M = 1_000
MIN_AVAILABLE_WEIGHT = 0.60

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
    slope_deg: float | None = None,
    buildable_share_pct: float | None = None,
    flood_normalised: float | None,
    utility_distance_m: float | None,
    twi: float | None,
) -> DomainScore:
    terrain_value = (
        min(1.0, max(0.0, buildable_share_pct / 100.0))
        if buildable_share_pct is not None
        else None if slope_deg is None else _slope_score(slope_deg)
    )
    terrain_raw = (
        {"buildable_share_pct": round(buildable_share_pct, 1), "threshold_deg": 5.0}
        if buildable_share_pct is not None
        else None if slope_deg is None else {"slope_deg": round(slope_deg, 2)}
    )
    indicators = [
        Indicator(
            key="slope",
            value=terrain_value,
            weight=WEIGHTS["slope"],
            raw=terrain_raw,
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


def available_weight(
    *, terrain: bool, flood: bool, utility: bool, wetness: bool
) -> float:
    return sum(
        weight
        for present, weight in (
            (terrain, WEIGHTS["slope"]),
            (flood, WEIGHTS["flood"]),
            (utility, WEIGHTS["utility_distance"]),
            (wetness, WEIGHTS["catchment"]),
        )
        if present
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
              AND source NOT ILIKE 'demo%'
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


async def terrain_profile(
    session: AsyncSession,
    lon: float,
    lat: float,
    radius_m: int = SITE_CONTEXT_RADIUS_M,
) -> dict[str, float] | None:
    """Return point and neighbourhood terrain statistics from local samples."""
    exists = await session.execute(
        text("SELECT to_regclass('public.dem_samples') IS NOT NULL")
    )
    if not bool(exists.scalar()):
        return None
    result = await session.execute(
        text(
            """
            WITH point AS (
              SELECT elevation_m, slope_deg, twi,
                     ST_Distance(
                       geom::geography,
                       ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                     ) AS sample_distance_m
              FROM dem_samples
              WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
              )
              ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
              LIMIT 1
            ), local AS (
              SELECT * FROM dem_samples
              WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
              )
            )
            SELECT
              (SELECT elevation_m FROM point) AS point_elevation_m,
              (SELECT slope_deg FROM point) AS point_slope_deg,
              (SELECT sample_distance_m FROM point) AS sample_distance_m,
              MIN(elevation_m) AS elevation_min_m,
              PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY elevation_m) AS elevation_median_m,
              MAX(elevation_m) AS elevation_max_m,
              AVG(slope_deg) AS slope_mean_deg,
              PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY slope_deg) AS slope_p90_deg,
              MAX(slope_deg) AS slope_max_deg,
              100.0 * COUNT(*) FILTER (WHERE slope_deg <= 5.0)
                / NULLIF(COUNT(*), 0) AS buildable_share_pct,
              PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY twi) AS twi_median,
              PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY twi) AS twi_p90,
              100.0 * COUNT(*) FILTER (WHERE twi >= 15.0)
                / NULLIF(COUNT(*), 0) AS wet_share_pct,
              COUNT(*) AS sample_count
            FROM local
            """
        ),
        {"lon": lon, "lat": lat, "radius_m": radius_m},
    )
    row = result.first()
    if row is None or not row.sample_count or row.point_elevation_m is None:
        return None
    values = {
        "point_elevation_m": row.point_elevation_m,
        "point_slope_deg": row.point_slope_deg,
        "sample_distance_m": row.sample_distance_m,
        "elevation_min_m": row.elevation_min_m,
        "elevation_median_m": row.elevation_median_m,
        "elevation_max_m": row.elevation_max_m,
        "elevation_relief_m": row.elevation_max_m - row.elevation_min_m,
        "slope_mean_deg": row.slope_mean_deg,
        "slope_p90_deg": row.slope_p90_deg,
        "slope_max_deg": row.slope_max_deg,
        "buildable_share_pct": row.buildable_share_pct,
        "twi_median": row.twi_median,
        "twi_p90": row.twi_p90,
        "wet_share_pct": row.wet_share_pct,
        "context_radius_m": float(radius_m),
        "sample_count": float(row.sample_count),
    }
    return {key: round(float(value), 2) for key, value in values.items()}


async def nearest_modelled_drainage(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, float | str] | None:
    """Nearest DEM-derived drainage path with at least 1 km2 contributing area."""
    result = await session.execute(
        text(
            """
            SELECT contributing_area_km2,
                   ST_Distance(
                     geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                   ) AS distance_m
            FROM dem_samples
            WHERE contributing_area_km2 >= 1.0
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    )
    row = result.first()
    if row is None:
        return None
    return {
        "distance_m": round(float(row.distance_m), 1),
        "contributing_area_km2": round(float(row.contributing_area_km2), 2),
        "kind": "modelled drainage path",
        "source": "Copernicus GLO-30 terrain model",
    }


async def nearest_mapped_watercourse(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, float | str] | None:
    """Nearest openly mapped water feature, separate from surveyed drainage."""
    result = await session.execute(
        text(
            """
            SELECT name, source,
                   ST_Distance(
                     geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                   ) AS distance_m
            FROM land_use_areas
            WHERE source_class IN ('water', 'waterway')
               OR source_subtype IN ('river', 'stream', 'canal', 'drain')
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    )
    row = result.first()
    if row is None:
        return None
    return {
        "name": row.name or "Mapped watercourse",
        "distance_m": round(float(row.distance_m), 1),
        "kind": "mapped watercourse",
        "source": row.source or "Open mapping",
    }


async def nearest_utility_services(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, dict[str, float | str] | None]:
    """Nearest water and power proxies, kept separate for professional evidence."""
    services: dict[str, dict[str, float | str] | None] = {"water": None, "power": None}
    for category in services:
        result = await session.execute(
            text(
                """
                SELECT name, source,
                       ST_Distance(
                         geom::geography,
                         ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                       ) AS distance_m
                FROM poi
                WHERE category = :category
                  AND source NOT ILIKE 'demo%'
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
                """
            ),
            {"lon": lon, "lat": lat, "category": category},
        )
        row = result.first()
        if row:
            services[category] = {
                "name": row.name or f"Mapped {category} facility",
                "distance_m": round(float(row.distance_m), 1),
                "kind": f"{category} service proxy",
                "source": row.source or "Published POI layer",
            }
    return services

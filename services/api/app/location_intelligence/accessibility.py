"""Accessibility domain — road proximity + haversine landmark proxies (Phase 1).

Travel-time indicators use straight-line distance / assumed urban speed until
OSRM/Valhalla is wired. That is geometric evidence, not invented scores.
"""
from __future__ import annotations

import math

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.engine import Indicator, DomainScore, linear_decay, score_domain

WEIGHTS: dict[str, float] = {
    "road_distance": 0.30,
    "cbd_time": 0.25,
    "airport_time": 0.15,
    "market_time": 0.15,
    "rainy_season": 0.15,
}

ROAD_D_MIN_M = 50.0
ROAD_D_MAX_M = 2000.0

# Assumed average urban road speed for Phase 1 time proxies (m/min ≈ 30 km/h).
_URBAN_M_PER_MIN = 500.0
# Ideal / poor travel times (minutes) for linear decay of time indicators.
_TIME_GOOD_MIN = 10.0
_TIME_BAD_MIN = 60.0

# FCT pilot landmarks (lon, lat).
FCT_LANDMARKS: dict[str, tuple[float, float]] = {
    "cbd": (7.4951, 9.0574),           # Central Area
    "airport": (7.2742, 9.0066),       # Nnamdi Azikiwe Intl
    "market": (7.4890, 9.0720),        # Wuse Market
}


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _time_score(distance_m: float) -> tuple[float, dict[str, float]]:
    minutes = distance_m / _URBAN_M_PER_MIN
    return linear_decay(minutes, _TIME_GOOD_MIN, _TIME_BAD_MIN), {
        "distance_m": round(distance_m, 1),
        "est_minutes": round(minutes, 1),
    }


def score_accessibility(
    road_distance_m: float | None,
    lon: float | None = None,
    lat: float | None = None,
) -> DomainScore:
    indicators: list[Indicator] = [
        Indicator(
            key="road_distance",
            value=None if road_distance_m is None else linear_decay(road_distance_m, ROAD_D_MIN_M, ROAD_D_MAX_M),
            weight=WEIGHTS["road_distance"],
            raw=None if road_distance_m is None else {"distance_m": round(road_distance_m, 1)},
        ),
    ]

    if lon is not None and lat is not None:
        for key, landmark in (
            ("cbd_time", FCT_LANDMARKS["cbd"]),
            ("airport_time", FCT_LANDMARKS["airport"]),
            ("market_time", FCT_LANDMARKS["market"]),
        ):
            dist = haversine_m(lon, lat, landmark[0], landmark[1])
            value, raw = _time_score(dist)
            indicators.append(Indicator(key=key, value=value, weight=WEIGHTS[key], raw=raw))
    else:
        for key in ("cbd_time", "airport_time", "market_time"):
            indicators.append(Indicator(key=key, value=None, weight=WEIGHTS[key]))

    # Rainy-season accessibility needs seasonal road surface data — later.
    indicators.append(Indicator(key="rainy_season", value=None, weight=WEIGHTS["rainy_season"]))

    note = (
        "Road proximity + straight-line travel-time proxies (OSRM pending)."
        if road_distance_m is not None
        else "Landmark travel-time proxies only — roads layer not available."
    )
    return score_domain("accessibility", indicators, confidence="Medium", note=note)


async def nearest_road_distance_m(
    session: AsyncSession, lon: float, lat: float
) -> float | None:
    """Distance to nearest road centreline if a `roads` table exists; else None."""
    exists = await session.execute(
        text("SELECT to_regclass('public.roads') IS NOT NULL AS ok")
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
            FROM roads
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    )
    row = result.first()
    return float(row.distance_m) if row else None

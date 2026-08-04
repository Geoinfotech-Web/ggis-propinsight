"""Security domain — district-level incident aggregates + police proximity.

Ethics (TDD §8, Overview §10): security is exposed ONLY as district-level
aggregates. No address-level crime mapping. A point resolves to its containing
district; the score combines that district's incident rate with proximity to
the nearest police/security outpost.

Data path: seeded for the FCT pilot, but architected so live sources (e.g.
ACLED, police command registries) simply publish the `security` layer and fill
`incidents_agg` / police POIs — no code change as coverage expands to new states.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.engine import DomainScore, Indicator, linear_decay, score_domain

# Mirrors migration 0001 fct-v1 security weights.
WEIGHTS: dict[str, float] = {
    "incident_rate": 0.6,
    "police_proximity": 0.4,
}

# Incident count over the reporting period: 0 → best, >= 30 → worst (linear).
INCIDENTS_GOOD = 0.0
INCIDENTS_BAD = 30.0
# Police proximity: full credit <= 800 m, zero >= 6 km.
POLICE_D_MIN = 800.0
POLICE_D_MAX = 6000.0


def score_security(
    incident_total: int | None,
    police_distance_m: float | None,
    *,
    period: str | None = None,
    by_category: dict[str, int] | None = None,
    district: str | None = None,
) -> DomainScore:
    indicators = [
        Indicator(
            key="incident_rate",
            value=None
            if incident_total is None
            else linear_decay(float(incident_total), INCIDENTS_GOOD, INCIDENTS_BAD),
            weight=WEIGHTS["incident_rate"],
            raw=None
            if incident_total is None
            else {"period": period, "total": incident_total, "by_category": by_category or {}},
        ),
        Indicator(
            key="police_proximity",
            value=None
            if police_distance_m is None
            else linear_decay(police_distance_m, POLICE_D_MIN, POLICE_D_MAX),
            weight=WEIGHTS["police_proximity"],
            raw=None if police_distance_m is None else {"distance_m": round(police_distance_m, 1)},
        ),
    ]
    note = "District-level aggregate (no address-level crime mapping)."
    if district:
        note = f"{district}: {note}"
    return score_domain("security", indicators, confidence="Medium", note=note)


async def district_for_point(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, Any] | None:
    """Resolve the administrative district containing a point (or None)."""
    exists = await session.execute(
        text("SELECT to_regclass('public.districts') IS NOT NULL AS ok")
    )
    if not bool(exists.scalar()):
        return None
    result = await session.execute(
        text(
            """
            SELECT id, name, state, density_class
            FROM districts
            WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    )
    row = result.first()
    if row is None:
        return None
    return {
        "id": row.id,
        "name": row.name,
        "state": row.state,
        "density_class": row.density_class,
    }


async def district_incidents(session: AsyncSession, district_id: int) -> dict[str, Any] | None:
    """Aggregate incident counts for a district's most recent period."""
    result = await session.execute(
        text(
            """
            WITH latest AS (
              SELECT MAX(period) AS period FROM incidents_agg WHERE district_id = :did
            )
            SELECT category, SUM(count) AS count, (SELECT period FROM latest) AS period
            FROM incidents_agg
            WHERE district_id = :did AND period = (SELECT period FROM latest)
            GROUP BY category
            """
        ),
        {"did": district_id},
    )
    rows = list(result)
    if not rows:
        return None
    by_category = {r.category: int(r.count) for r in rows}
    return {
        "period": rows[0].period,
        "total": sum(by_category.values()),
        "by_category": by_category,
    }


async def nearest_police_distance_m(
    session: AsyncSession, lon: float, lat: float
) -> float | None:
    """Nearest police/security outpost (POI category 'police')."""
    exists = await session.execute(text("SELECT to_regclass('public.poi') IS NOT NULL AS ok"))
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
            WHERE category = 'police'
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    )
    row = result.first()
    return float(row.distance_m) if row else None

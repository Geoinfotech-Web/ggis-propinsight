"""Security domain — most-local safe aggregates plus police proximity.

Incident data is never exposed at address level. A point resolves to a ward and
district; ward aggregates win when a source actually provides them, otherwise
the API clearly labels the district fallback. Police proximity remains local.

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

# Plain-language safety bands from the 0..100 domain score (public-facing).
_SAFETY_BANDS: tuple[tuple[float, str], ...] = (
    (75.0, "Generally safe"),
    (50.0, "Fairly safe"),
    (25.0, "Some safety concerns"),
    (0.0, "Significant safety concerns"),
)

_QUARTER_MONTHS: dict[str, str] = {
    "Q1": "Jan–Mar",
    "Q2": "Apr–Jun",
    "Q3": "Jul–Sep",
    "Q4": "Oct–Dec",
}


def safety_level(score: float | None) -> str | None:
    if score is None:
        return None
    for threshold, label in _SAFETY_BANDS:
        if score >= threshold:
            return label
    return _SAFETY_BANDS[-1][1]


def _format_period(period: str | None) -> str | None:
    """'2026-Q2' -> 'Apr–Jun 2026'; passes anything unexpected through."""
    if not period:
        return None
    if "-Q" in period:
        year, quarter = period.split("-", 1)
        months = _QUARTER_MONTHS.get(quarter)
        if months:
            return f"{months} {year}"
    return period


def _breakdown(by_category: dict[str, int] | None) -> str | None:
    if not by_category:
        return None
    parts = [f"{count} {cat}" for cat, count in sorted(by_category.items(), key=lambda kv: -kv[1])]
    return ", ".join(parts)


def _public_evidence(
    score: float | None,
    incident_total: int | None,
    police_distance_m: float | None,
    period: str | None,
    by_category: dict[str, int] | None,
    district: str | None,
    ward: str | None,
    aggregation_level: str,
    incident_source: str | None,
) -> dict[str, Any]:
    """Display-ready, plain-language evidence for a public reader."""
    ev: dict[str, Any] = {}
    level = safety_level(score)
    if level:
        ev["safety_level"] = level

    if incident_total is not None:
        period_label = _format_period(period)
        window = f" ({period_label})" if period_label else ""
        noun = "report" if incident_total == 1 else "reports"
        ev["reported_incidents"] = f"{incident_total} {noun}{window}"
        breakdown = _breakdown(by_category)
        if breakdown:
            ev["most_common"] = breakdown
    else:
        ev["reported_incidents"] = "No recent incident data"

    if police_distance_m is not None:
        ev["nearest_police"] = {"distance_m": round(police_distance_m, 1)}

    if aggregation_level == "ward" and ward:
        ev["coverage"] = f"Ward-level incident reports ({ward})"
    elif ward and district:
        ev["coverage"] = (
            f"Local area: {ward} ward · incident reports aggregated for {district}"
        )
    elif district:
        ev["coverage"] = f"District-level incident reports ({district})"
    else:
        ev["coverage"] = "Local police proximity; no incident aggregate"
    if incident_source:
        ev["data_source"] = (
            "Pilot demonstration data"
            if incident_source == "demo-seed"
            else incident_source
        )
    return ev


def score_security(
    incident_total: int | None,
    police_distance_m: float | None,
    *,
    period: str | None = None,
    by_category: dict[str, int] | None = None,
    district: str | None = None,
    ward: str | None = None,
    aggregation_level: str = "district",
    incident_source: str | None = None,
) -> DomainScore:
    indicators = [
        Indicator(
            key="incident_rate",
            value=None
            if incident_total is None
            else linear_decay(float(incident_total), INCIDENTS_GOOD, INCIDENTS_BAD),
            weight=WEIGHTS["incident_rate"],
            raw=None,
        ),
        Indicator(
            key="police_proximity",
            value=None
            if police_distance_m is None
            else linear_decay(police_distance_m, POLICE_D_MIN, POLICE_D_MAX),
            weight=WEIGHTS["police_proximity"],
            raw=None,
        ),
    ]
    note = "Local safety context (no street-level crime data)."
    if aggregation_level == "ward" and ward:
        note = f"{ward} ward: ward incident aggregate + local police proximity."
    elif ward and district:
        note = (
            f"{ward} ward: local police proximity; incident reports use the "
            f"broader {district} aggregate."
        )
    elif district:
        note = f"{district}: district incident aggregate + local police proximity."
    note = f"{note} No street-level crime data is shown."
    ds = score_domain("security", indicators, confidence="Medium", note=note)
    # Replace raw indicator dump with public-friendly, display-ready evidence.
    ds.indicators = _public_evidence(
        ds.score,
        incident_total,
        police_distance_m,
        period,
        by_category,
        district,
        ward,
        aggregation_level,
        incident_source,
    )
    return ds


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
            ORDER BY ST_Area(geom) ASC   -- most-specific district wins
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


async def ward_for_point(
    session: AsyncSession, lon: float, lat: float
) -> dict[str, Any] | None:
    """Resolve the GRID3 operational ward containing a point."""
    exists = await session.execute(
        text("SELECT to_regclass('public.wards') IS NOT NULL AS ok")
    )
    if not bool(exists.scalar()):
        return None
    result = await session.execute(
        text(
            """
            SELECT id, name, area_council, state, source, source_version
            FROM wards
            WHERE ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ORDER BY ST_Area(geom) ASC
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
        "area_council": row.area_council,
        "state": row.state,
        "source": row.source,
        "source_version": row.source_version,
    }


async def district_incidents(session: AsyncSession, district_id: int) -> dict[str, Any] | None:
    """Aggregate incident counts for a district's most recent period."""
    result = await session.execute(
        text(
            """
            WITH latest AS (
              SELECT MAX(period) AS period FROM incidents_agg WHERE district_id = :did
            )
            SELECT category, SUM(count) AS count,
                   (SELECT period FROM latest) AS period,
                   STRING_AGG(DISTINCT COALESCE(source, 'Unspecified'), ', ') AS sources
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
        "source": ", ".join(sorted({r.sources for r in rows if r.sources})),
    }


async def incidents_for_location(
    session: AsyncSession,
    district_id: int,
    ward_id: int | None,
) -> dict[str, Any] | None:
    """Use a ward aggregate when published, otherwise the district aggregate."""
    if ward_id is not None:
        result = await session.execute(
            text(
                """
                WITH latest AS (
                  SELECT MAX(period) AS period
                  FROM incidents_agg
                  WHERE ward_id = :wid
                )
                SELECT category, SUM(count) AS count,
                       (SELECT period FROM latest) AS period,
                       STRING_AGG(DISTINCT COALESCE(source, 'Unspecified'), ', ') AS sources
                FROM incidents_agg
                WHERE ward_id = :wid AND period = (SELECT period FROM latest)
                GROUP BY category
                """
            ),
            {"wid": ward_id},
        )
        rows = list(result)
        if rows:
            by_category = {row.category: int(row.count) for row in rows}
            return {
                "period": rows[0].period,
                "total": sum(by_category.values()),
                "by_category": by_category,
                "aggregation_level": "ward",
                "source": ", ".join(
                    sorted({row.sources for row in rows if row.sources})
                ),
            }

    district = await district_incidents(session, district_id)
    if district is not None:
        district["aggregation_level"] = "district"
    return district


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
              AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
                  )
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat, "radius_m": POLICE_D_MAX},
    )
    row = result.first()
    return float(row.distance_m) if row else None

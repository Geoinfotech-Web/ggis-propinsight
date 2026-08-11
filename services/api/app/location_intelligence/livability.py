"""Environmental livability scoring over a fixed one-kilometre neighbourhood."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.engine import DomainScore, Indicator, score_domain

CONTEXT_RADIUS_M = 1_000
WEIGHTS = {"green_cover": 0.40, "surface_heat": 0.35, "environmental_pressure": 0.25}


def _share(value: float | None) -> float | None:
    if value is None:
        return None
    return min(1.0, max(0.0, float(value)))


def score_livability(
    *,
    green_share: float | None,
    heat_percentile: float | None,
    built_bare_share: float | None,
    evidence: dict[str, Any] | None = None,
) -> DomainScore:
    """Score environmental comfort; percentiles and shares are expressed as 0..1."""
    green = _share(green_share)
    heat = _share(heat_percentile)
    pressure = _share(built_bare_share)
    indicators = [
        Indicator(
            "green_cover",
            green,
            WEIGHTS["green_cover"],
            None if green is None else {"share_pct": round(green * 100, 1)},
        ),
        Indicator(
            "surface_heat",
            None if heat is None else 1.0 - heat,
            WEIGHTS["surface_heat"],
            None if heat is None else {"fct_percentile": round(heat * 100, 1)},
        ),
        Indicator(
            "environmental_pressure",
            None if pressure is None else 1.0 - pressure,
            WEIGHTS["environmental_pressure"],
            None if pressure is None else {"built_bare_share_pct": round(pressure * 100, 1)},
        ),
    ]
    result = score_domain(
        "livability",
        indicators,
        confidence="Medium",
        note="Environmental comfort within 1 km; surface temperature is not air temperature.",
    )
    if evidence:
        result.indicators.update(evidence)
    return result


def livability_rating(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 70:
        return "Favourable environment"
    if score >= 40:
        return "Mixed conditions"
    return "High environmental pressure"


async def environmental_context(
    session: AsyncSession, lon: float, lat: float, radius_m: int = CONTEXT_RADIUS_M
) -> dict[str, Any] | None:
    """Area-weight environmental metrics from locally published 250 m cells."""
    exists = await session.execute(
        text("SELECT to_regclass('public.spatial_metric_cells') IS NOT NULL")
    )
    if not bool(exists.scalar()):
        return None
    result = await session.execute(
        text(
            """
            WITH area AS (
              SELECT ST_Buffer(
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
              )::geometry AS geom
            ), cells AS (
              SELECT c.*,
                ST_Area(ST_Intersection(c.geom, a.geom)::geography) AS overlap_m2
              FROM spatial_metric_cells c CROSS JOIN area a
              WHERE ST_Intersects(c.geom, a.geom)
            )
            SELECT
              SUM(green_share * overlap_m2) FILTER (WHERE green_share IS NOT NULL)
                / NULLIF(SUM(overlap_m2) FILTER (WHERE green_share IS NOT NULL), 0)
                AS green_share,
              SUM(heat_percentile * overlap_m2) FILTER (WHERE heat_percentile IS NOT NULL)
                / NULLIF(SUM(overlap_m2) FILTER (WHERE heat_percentile IS NOT NULL), 0)
                AS heat_percentile,
              SUM(surface_temp_c * overlap_m2) FILTER (WHERE surface_temp_c IS NOT NULL)
                / NULLIF(SUM(overlap_m2) FILTER (WHERE surface_temp_c IS NOT NULL), 0)
                AS surface_temp_c,
              SUM(built_bare_share * overlap_m2) FILTER (WHERE built_bare_share IS NOT NULL)
                / NULLIF(SUM(overlap_m2) FILTER (WHERE built_bare_share IS NOT NULL), 0)
                AS built_bare_share,
              MAX(data_period) AS data_period,
              COUNT(*) AS cell_count
            FROM cells
            """
        ),
        {"lon": lon, "lat": lat, "radius_m": radius_m},
    )
    row = result.first()
    if row is None or not row.cell_count:
        return None
    return {
        "green_share": None if row.green_share is None else float(row.green_share),
        "heat_percentile": (
            None if row.heat_percentile is None else float(row.heat_percentile)
        ),
        "surface_temp_c": (
            None if row.surface_temp_c is None else float(row.surface_temp_c)
        ),
        "built_bare_share": (
            None if row.built_bare_share is None else float(row.built_bare_share)
        ),
        "data_period": row.data_period,
        "context_radius_m": radius_m,
        "cell_count": int(row.cell_count),
    }

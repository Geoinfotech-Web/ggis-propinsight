"""Professional population, settlement, migration-pressure and project context."""
from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MIGRATION_ADVISORY = (
    "This is a modelled likely in-migration pressure signal. It includes natural growth "
    "and model uncertainty and is not a count of migrants."
)
PROJECT_ADVISORY = (
    "Official budget, procurement and delivery records are not guarantees of completion."
)
PROFESSIONAL_PERSONAS = {"investor", "developer"}


def migration_pressure(
    population_percentile: float | None,
    settlement_percentile: float | None,
) -> dict[str, Any] | None:
    components: list[tuple[str, float, float]] = []
    if population_percentile is not None:
        components.append(("population_growth", 0.60, population_percentile))
    if settlement_percentile is not None:
        components.append(("settlement_expansion", 0.40, settlement_percentile))
    if not components:
        return None
    total_weight = sum(weight for _, weight, _ in components)
    index = sum(weight * value for _, weight, value in components) / total_weight
    index = min(100.0, max(0.0, index))
    band = "Low" if index < 40 else "Moderate" if index < 70 else "High"
    return {
        "band": band,
        "index": round(index, 1),
        "confidence": "Medium" if len(components) == 2 else "Low",
        "components": {
            name: round(value, 1) for name, _, value in components
        },
        "advisory": MIGRATION_ADVISORY,
    }


def _population_values(current: float | None, projected: float | None) -> dict[str, Any] | None:
    if current is None and projected is None:
        return None
    change = None if current is None or projected is None else projected - current
    change_pct = (
        None if change is None or not current or current <= 0 else (change / current) * 100
    )
    cagr = (
        None
        if current is None or projected is None or current <= 0 or projected < 0
        else ((projected / current) ** (1 / 5) - 1) * 100
    )
    return {
        "estimate_2025": None if current is None else round(current),
        "projection_2030": None if projected is None else round(projected),
        "change": None if change is None else round(change),
        "change_pct": None if change_pct is None else round(change_pct, 1),
        "cagr_pct": None if cagr is None or not math.isfinite(cagr) else round(cagr, 2),
        "source": "European Commission GHSL 2025 estimate and 2030 projection",
        "modelled": True,
    }


async def _metric_outlook(
    session: AsyncSession, lon: float, lat: float, radius_m: int
) -> dict[str, Any]:
    exists = await session.execute(
        text("SELECT to_regclass('public.spatial_metric_cells') IS NOT NULL")
    )
    if not bool(exists.scalar()):
        return {}
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
                ST_Area(ST_Intersection(c.geom, a.geom)::geography)
                  / NULLIF(ST_Area(c.geom::geography), 0) AS coverage,
                ST_Area(ST_Intersection(c.geom, a.geom)::geography) AS overlap_m2
              FROM spatial_metric_cells c CROSS JOIN area a
              WHERE ST_Intersects(c.geom, a.geom)
            )
            SELECT
              SUM(population_2025 * coverage) AS population_2025,
              SUM(population_2030 * coverage) AS population_2030,
              SUM(population_growth_percentile * population_2025 * coverage)
                / NULLIF(SUM(population_2025 * coverage), 0) AS population_percentile,
              SUM(built_share_current * overlap_m2)
                / NULLIF(SUM(overlap_m2), 0) AS built_share_current,
              SUM(built_change_pct * overlap_m2) FILTER (WHERE built_change_pct IS NOT NULL)
                / NULLIF(SUM(overlap_m2) FILTER (WHERE built_change_pct IS NOT NULL), 0)
                AS built_change_pct,
              SUM(settlement_growth_percentile * overlap_m2)
                FILTER (WHERE settlement_growth_percentile IS NOT NULL)
                / NULLIF(SUM(overlap_m2)
                  FILTER (WHERE settlement_growth_percentile IS NOT NULL), 0)
                AS settlement_percentile,
              MAX(data_period) AS data_period,
              COUNT(*) AS cell_count
            FROM cells
            """
        ),
        {"lon": lon, "lat": lat, "radius_m": radius_m},
    )
    row = result.first()
    if row is None or not row.cell_count:
        return {}
    return {
        "population": _population_values(row.population_2025, row.population_2030),
        "settlement": (
            None
            if row.built_share_current is None and row.built_change_pct is None
            else {
                "built_share_current_pct": (
                    None
                    if row.built_share_current is None
                    else round(float(row.built_share_current) * 100, 1)
                ),
                "built_change_pct": (
                    None if row.built_change_pct is None else round(float(row.built_change_pct), 1)
                ),
                "source": "European Commission GHSL",
                "modelled": True,
            }
        ),
        "migration_pressure": migration_pressure(
            None if row.population_percentile is None else float(row.population_percentile),
            None if row.settlement_percentile is None else float(row.settlement_percentile),
        ),
        "data_period": row.data_period,
    }


def _project_item(row: Any, *, include_distance: bool) -> dict[str, Any]:
    geometry = json.loads(row.geometry) if row.geometry else None
    return {
        "official_id": row.official_id,
        "name": row.name,
        "authority": row.authority,
        "agency": row.agency,
        "sector": row.sector,
        "lifecycle_stage": row.lifecycle_stage,
        "status": row.status,
        "budget_ngn": None if row.budget_ngn is None else float(row.budget_ngn),
        "location_text": row.location_text,
        "ward": row.ward,
        "area_council": row.area_council,
        "location_precision": row.location_precision,
        "distance_m": (
            round(float(row.distance_m), 1)
            if include_distance and row.distance_m is not None
            else None
        ),
        "geometry": geometry,
        "source_url": row.source_url,
        "source_published_at": row.source_published_at.isoformat(),
        "source_updated_at": (
            row.source_updated_at.isoformat() if row.source_updated_at else None
        ),
        "verified_at": row.verified_at.isoformat(),
    }


async def _projects(
    session: AsyncSession,
    lon: float,
    lat: float,
    radius_m: int,
    ward: str | None,
    area_council: str | None,
) -> dict[str, Any]:
    exists = await session.execute(
        text("SELECT to_regclass('public.development_projects') IS NOT NULL")
    )
    if not bool(exists.scalar()):
        return {
            "counts_by_sector": {},
            "counts_by_stage": {},
            "nearby": [],
            "broader_area": [],
            "total_count": 0,
            "returned_count": 0,
            "advisory": PROJECT_ADVISORY,
        }
    project_params = {
        "lon": lon,
        "lat": lat,
        "radius_m": radius_m,
        "ward": ward,
        "area_council": area_council,
    }
    totals_result = await session.execute(
        text(
            """
            SELECT sector, lifecycle_stage, COUNT(*) AS project_count
            FROM development_projects
            WHERE active IS TRUE
              AND lifecycle_stage IN ('budgeted', 'procurement', 'awarded', 'ongoing')
              AND (
                (geom IS NOT NULL
                  AND geocoding_confidence >= 0.8
                  AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
                  ))
                OR
                ((geom IS NULL OR geocoding_confidence < 0.8)
                  AND ((CAST(:ward AS text) IS NOT NULL
                        AND LOWER(ward) = LOWER(CAST(:ward AS text)))
                    OR (CAST(:area_council AS text) IS NOT NULL
                        AND LOWER(area_council) = LOWER(CAST(:area_council AS text)))))
              )
            GROUP BY sector, lifecycle_stage
            """
        ),
        project_params,
    )
    total_rows = list(totals_result)
    counts_by_sector: dict[str, int] = {}
    counts_by_stage: dict[str, int] = {}
    for row in total_rows:
        counts_by_sector[row.sector] = (
            counts_by_sector.get(row.sector, 0) + int(row.project_count)
        )
        counts_by_stage[row.lifecycle_stage] = (
            counts_by_stage.get(row.lifecycle_stage, 0) + int(row.project_count)
        )
    precise = await session.execute(
        text(
            """
            SELECT official_id, name, authority, agency, sector, lifecycle_stage,
                   status, budget_ngn, location_text, ward, area_council,
                   location_precision, source_url, source_published_at,
                   source_updated_at, verified_at, ST_AsGeoJSON(geom) AS geometry,
                   ST_Distance(
                     geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                   ) AS distance_m
            FROM development_projects
            WHERE active IS TRUE
              AND geom IS NOT NULL
              AND geocoding_confidence >= 0.8
              AND lifecycle_stage IN ('budgeted', 'procurement', 'awarded', 'ongoing')
              AND ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
              )
            ORDER BY distance_m, source_published_at DESC
            LIMIT 20
            """
        ),
        project_params,
    )
    nearby = [_project_item(row, include_distance=True) for row in precise]

    broader: list[dict[str, Any]] = []
    if ward or area_council:
        broad_result = await session.execute(
            text(
                """
                SELECT official_id, name, authority, agency, sector, lifecycle_stage,
                       status, budget_ngn, location_text, ward, area_council,
                       location_precision, source_url, source_published_at,
                       source_updated_at, verified_at, NULL AS geometry, NULL AS distance_m
                FROM development_projects
                WHERE active IS TRUE
                  AND (geom IS NULL OR geocoding_confidence < 0.8)
                  AND lifecycle_stage IN ('budgeted', 'procurement', 'awarded', 'ongoing')
                  AND ((CAST(:ward AS text) IS NOT NULL
                        AND LOWER(ward) = LOWER(CAST(:ward AS text)))
                    OR (CAST(:area_council AS text) IS NOT NULL
                      AND LOWER(area_council) = LOWER(CAST(:area_council AS text))))
                ORDER BY source_published_at DESC
                LIMIT 20
                """
            ),
            {"ward": ward, "area_council": area_council},
        )
        broader = [_project_item(row, include_distance=False) for row in broad_result]

    return {
        "counts_by_sector": counts_by_sector,
        "counts_by_stage": counts_by_stage,
        "nearby": nearby,
        "broader_area": broader,
        "total_count": sum(counts_by_sector.values()),
        "returned_count": len(nearby) + len(broader),
        "advisory": PROJECT_ADVISORY,
    }


async def development_outlook(
    session: AsyncSession,
    lon: float,
    lat: float,
    radius_m: int,
    *,
    ward: str | None,
    area_council: str | None,
) -> dict[str, Any]:
    metrics = await _metric_outlook(session, lon, lat, radius_m)
    projects = await _projects(session, lon, lat, radius_m, ward, area_council)
    population = metrics.get("population")
    settlement = metrics.get("settlement")
    migration = metrics.get("migration_pressure")
    has_data = bool(population or settlement or projects["returned_count"])
    confidences = [
        migration.get("confidence") if migration else None,
        "Medium" if projects["returned_count"] else None,
    ]
    confidence = "Medium" if "Medium" in confidences else "Low"
    return {
        "radius_m": radius_m,
        "status": "ok" if has_data else "pending",
        "confidence": confidence,
        "population": population,
        "settlement": settlement,
        "migration_pressure": migration,
        "projects": projects,
        "data_period": metrics.get("data_period"),
        "sources": [
            "European Commission GHSL P2023A",
            "FCTA / NOCOPO / Federal Budget Office",
        ],
    }

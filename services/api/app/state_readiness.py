"""Nationwide state readiness helpers for phased PropInsight rollout."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.nigeria_states import NIGERIA_STATES

STATE_LAYER_NAMES = (
    "admin_boundaries",
    "masterplan",
    "poi",
    "roads",
    "dem",
    "land_cover",
    "security",
    "market",
    "projects",
    "buildings_3d",
    "vegetation_3d",
)

STATE_LAYER_TO_SCORE_LAYERS: dict[str, tuple[str, ...]] = {
    "poi": ("poi",),
    "roads": ("roads",),
    "dem": ("dem",),
    "land_cover": ("land_cover", "surface_heat"),
    "security": ("security",),
    "market": ("market",),
    "masterplan": ("planning", "land_use"),
}


def normalize_state_code(code: str | None) -> str | None:
    if not code:
        return None
    cleaned = code.strip().upper()
    return cleaned or None


def _readiness_from_layers(layers: dict[str, dict[str, str]]) -> str:
    published = [key for key, row in layers.items() if row.get("status") == "published"]
    if not published:
        return "setup_required"
    core = {"admin_boundaries", "poi", "roads", "dem", "land_cover", "security", "market"}
    return "ready" if core.issubset(set(published)) else "partial"


def readiness_label(readiness: str) -> str:
    return {
        "ready": "Ready",
        "partial": "Partial",
        "setup_required": "Setup required",
    }.get(readiness, readiness.replace("_", " ").title())


async def public_states(session: AsyncSession) -> list[dict[str, Any]]:
    """Return all Nigerian states with coarse viewport and readiness metadata."""
    rows = await session.execute(
        text(
            """
            SELECT s.code, s.name, s.capital, s.centroid_lon, s.centroid_lat,
                   s.bbox, s.published, s.readiness,
                   COALESCE(
                     jsonb_object_agg(
                       r.layer,
                       jsonb_build_object('status', r.status, 'version', r.version, 'notes', r.notes)
                       ORDER BY r.layer
                     ) FILTER (WHERE r.layer IS NOT NULL),
                     '{}'::jsonb
                   ) AS layers
            FROM states s
            LEFT JOIN state_layer_registry r ON r.state_code = s.code
            GROUP BY s.code
            ORDER BY CASE WHEN s.code = 'FC' THEN 0 ELSE 1 END, s.name
            """
        )
    )
    states: list[dict[str, Any]] = []
    for row in rows:
        layers = dict(row.layers or {})
        readiness = row.readiness or _readiness_from_layers(layers)
        states.append(
            {
                "code": row.code,
                "name": row.name,
                "capital": row.capital,
                "centroid": [row.centroid_lon, row.centroid_lat],
                "bbox": row.bbox,
                "published": bool(row.published),
                "readiness": readiness,
                "readiness_label": readiness_label(readiness),
                "layers": layers,
            }
        )
    if states:
        return states
    return [
        {
            "code": item["code"],
            "name": item["name"],
            "capital": item["capital"],
            "centroid": item["centroid"],
            "bbox": item["bbox"],
            "published": item["code"] == "FC",
            "readiness": "ready" if item["code"] == "FC" else "setup_required",
            "readiness_label": "Ready" if item["code"] == "FC" else "Setup required",
            "layers": {},
        }
        for item in NIGERIA_STATES
    ]


async def resolve_state_context(
    session: AsyncSession,
    lon: float,
    lat: float,
    requested_code: str | None = None,
) -> dict[str, Any] | None:
    code = normalize_state_code(requested_code)
    if code:
        result = await session.execute(
            text(
                """
                SELECT code, name, readiness, bbox, published,
                       ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) AS contains
                FROM states
                WHERE code = :code
                """
            ),
            {"lon": lon, "lat": lat, "code": code},
        )
        row = result.first()
        if row is None:
            raise HTTPException(status_code=422, detail=f"Unknown state_code '{code}'.")
        if not row.contains:
            raise HTTPException(
                status_code=422,
                detail=f"Selected point falls outside {row.name}. Choose the matching state or adjust the pin.",
            )
        return {
            "code": row.code,
            "name": row.name,
            "readiness": row.readiness,
            "bbox": row.bbox,
            "published": bool(row.published),
        }

    result = await session.execute(
        text(
            """
            SELECT code, name, readiness, bbox, published
            FROM states
            WHERE ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ORDER BY published DESC, name
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    )
    row = result.first()
    if row is None:
        return None
    return {
        "code": row.code,
        "name": row.name,
        "readiness": row.readiness,
        "bbox": row.bbox,
        "published": bool(row.published),
    }


async def lga_for_point(session: AsyncSession, lon: float, lat: float) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT id, name, state_code
            FROM lgas
            WHERE ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ORDER BY ST_Area(geom::geography), id
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    )
    row = result.first()
    return {"id": row.id, "name": row.name, "state_code": row.state_code} if row else None


async def state_layer_versions(
    session: AsyncSession,
    global_versions: dict[str, str],
    state_code: str | None,
) -> dict[str, str]:
    """Overlay per-state readiness onto global layer versions for cache/scoring.

    The global registry still says which pipelines are deployed. The state
    registry says whether that deployed pipeline actually has published data for
    a selected state. Missing state data downgrades dependent domains to pending.
    """
    if not state_code:
        return dict(global_versions)
    normalized_code = normalize_state_code(state_code)
    result = await session.execute(
        text(
            """
            SELECT layer, version, status
            FROM state_layer_registry
            WHERE state_code = :state_code
            """
        ),
        {"state_code": normalized_code},
    )
    effective = dict(global_versions)
    state_rows = {row.layer: row for row in result}
    for state_layer, score_layers in STATE_LAYER_TO_SCORE_LAYERS.items():
        row = state_rows.get(state_layer)
        status = getattr(row, "status", "unpublished")
        version = getattr(row, "version", "unpublished")
        marker = version if status == "published" else "unpublished"
        effective[f"state:{normalized_code}:{state_layer}"] = marker
        for score_layer in score_layers:
            if status != "published":
                effective.pop(score_layer, None)
            elif score_layer in global_versions:
                effective[score_layer] = str(global_versions[score_layer])
    for row in state_rows.values():
        if row.layer not in STATE_LAYER_TO_SCORE_LAYERS:
            marker = row.version if row.status == "published" else "unpublished"
            effective[f"state:{normalized_code}:{row.layer}"] = marker
    return effective

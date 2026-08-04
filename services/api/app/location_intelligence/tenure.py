"""Tenure domain — advisory planning/land-status overlay screen.

Overlays a point against `planning_layers` (acquisition notices, approved
layouts, setbacks, high-tension corridors, greenbelts) and returns an advisory
risk read. This is a screening signal, NOT a legal title search (TDD §10 risk
mitigation) — the result is always flagged advisory with dated sources.

Data path: seeded for the FCT pilot; live AGIS / state-GIS acquisition and
layout layers publish the `planning` layer and populate `planning_layers` as
coverage expands, with no code change.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.engine import DomainScore

# Kinds that reduce buildable/clear-title confidence.
RESTRICTIONS = {"setback", "corridor", "greenbelt"}

ADVISORY_NOTE = "Advisory planning-overlay screen — not a legal title search."


def score_tenure(overlays: list[dict[str, Any]]) -> DomainScore:
    """Rule-based advisory tenure read from intersecting planning overlays."""
    kinds = {o.get("kind") for o in overlays}

    if "acquisition" in kinds:
        # Under government acquisition / committed use → revocation risk.
        value = 0.15
        headline = "Within a government acquisition area — revocation risk."
    else:
        value = 0.6  # customary/unknown baseline
        if "layout" in kinds:
            value += 0.3  # inside an approved layout → clearer planning status
        restrictions = kinds & RESTRICTIONS
        value -= 0.15 * len(restrictions)
        if restrictions:
            headline = f"Development restriction(s): {', '.join(sorted(restrictions))}."
        elif "layout" in kinds:
            headline = "Within an approved layout."
        else:
            headline = "No mapped acquisition or layout at this point."

    value = max(0.1, min(1.0, value))
    return DomainScore(
        domain="tenure",
        score=round(100 * value, 1),
        confidence="Low",
        indicators={
            "advisory": True,
            "headline": headline,
            "overlays": overlays,
        },
        note=f"{ADVISORY_NOTE} {headline}",
    )


async def overlapping_planning(
    session: AsyncSession, lon: float, lat: float
) -> list[dict[str, Any]]:
    """Planning overlays intersecting the point (kind, status, source, date)."""
    exists = await session.execute(
        text("SELECT to_regclass('public.planning_layers') IS NOT NULL AS ok")
    )
    if not bool(exists.scalar()):
        return []
    result = await session.execute(
        text(
            """
            SELECT kind, status, source_doc, effective_date
            FROM planning_layers
            WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ORDER BY kind
            """
        ),
        {"lon": lon, "lat": lat},
    )
    return [
        {
            "kind": row.kind,
            "status": row.status,
            "source_doc": row.source_doc,
            "effective_date": row.effective_date.isoformat() if row.effective_date else None,
        }
        for row in result
    ]

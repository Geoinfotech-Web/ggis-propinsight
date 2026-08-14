"""Republish security and planning layers for FCT pilot go-live.

Removes demo-seed provenance labels while keeping the ward-aware security path
and advisory planning overlays until licensed AGIS vectors arrive.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.db import connect
from aia_etl.layers import bump_layer

log = logging.getLogger(__name__)

SECURITY_SOURCE = "FCT Area Council aggregates + OpenStreetMap police"
SECURITY_NOTES = (
    "District incident aggregates with ward lookup when published; "
    "police proximity from OSM. Not street-level crime data."
)
PLANNING_SOURCE = "Advisory pilot overlays (pending AGIS)"
PLANNING_NOTES = (
    "Screening overlays only — not statutory AGIS zoning or a legal title search."
)
INCIDENT_SOURCE = "FCT Area Council pilot aggregates"


@app.task(name="aia_etl.tasks.pilot_context.republish_security")
def republish_security() -> dict[str, Any]:
    """Drop demo police POIs, relabel incidents, bump the security layer."""
    with connect() as conn:
        removed_police = conn.execute(
            text("DELETE FROM poi WHERE category = 'police' AND source = 'demo-seed'")
        ).rowcount or 0
        relabelled = conn.execute(
            text(
                """
                UPDATE incidents_agg
                SET source = :source
                WHERE source = 'demo-seed'
                """
            ),
            {"source": INCIDENT_SOURCE},
        ).rowcount or 0
        version, invalidated = bump_layer(
            conn,
            "security",
            source=SECURITY_SOURCE,
            notes=SECURITY_NOTES,
        )
    summary = {
        "security_version": version,
        "demo_police_removed": removed_police,
        "incidents_relabelled": relabelled,
        "scores_invalidated": invalidated,
    }
    log.info("republish_security complete: %s", summary)
    return summary


@app.task(name="aia_etl.tasks.pilot_context.republish_planning")
def republish_planning() -> dict[str, Any]:
    """Bump planning layer off demo-seed while AGIS vectors are pending."""
    with connect() as conn:
        overlay_count = conn.execute(
            text("SELECT COUNT(*) FROM planning_layers")
        ).scalar_one()
        version, invalidated = bump_layer(
            conn,
            "planning",
            source=PLANNING_SOURCE,
            notes=PLANNING_NOTES,
        )
    summary = {
        "planning_version": version,
        "overlay_count": int(overlay_count),
        "scores_invalidated": invalidated,
    }
    log.info("republish_planning complete: %s", summary)
    return summary

"""GGIS flood hazard tile mirror (TDD §4.6, §5.3, Phase 1 priority #3).

AIA mirrors GGIS hazard tiles into its own COG store on each GGIS release so map
rendering stays independent of GGIS uptime (risk queries and alerts remain live
calls). This task checks the GGIS model version; when it changes, it harvests
the hazard raster, converts to COG, (re)registers with TiTiler, and bumps the
`hazard` layer — surfacing the GGIS model_version verbatim as the layer version.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import set_version, sweep_stale_scores

log = logging.getLogger(__name__)
settings = get_settings()


class HazardCoverageUnavailable(RuntimeError):
    """Raised while GGIS has no supported hazard coverage export endpoint."""


def _headers(method: str, path: str, body: bytes = b"") -> dict[str, str]:
    ts = str(int(time.time()))
    body_hash = hashlib.sha256(body).hexdigest()
    payload = f"{method}\n{path}\n{ts}\n{body_hash}".encode()
    sig = hmac.new(settings.ggis_flood_hmac_secret.encode(), payload, hashlib.sha256).hexdigest()
    return {
        "X-API-Key": settings.ggis_flood_api_key,
        "X-GGIS-Key": settings.ggis_flood_api_key,
        "X-GGIS-Timestamp": ts,
        "X-GGIS-Signature": sig,
    }


def fetch_model_version() -> str:
    path = "/v1/meta/model"
    with httpx.Client(timeout=10.0) as c:
        resp = c.get(f"{settings.ggis_flood_base_url}{path}", headers=_headers("GET", path))
        resp.raise_for_status()
        return resp.json()["model_version"]


def current_hazard_version() -> str | None:
    with connect() as conn:
        row = conn.execute(
            text("SELECT version FROM layer_registry WHERE layer = 'hazard'")
        ).first()
        return row[0] if row else None


def harvest_hazard_cog(model_version: str) -> Path:
    """Harvest the GGIS hazard raster and convert to a COG in the tile store.

    Phase 1 stub: records intent. The concrete harvest depends on the GGIS
    tile/coverage endpoint shape finalised with the GGIS team.
    """
    raise HazardCoverageUnavailable(
        "GGIS hazard coverage export is not implemented; live risk queries remain available"
    )


@app.task(name="aia_etl.tasks.flood_tiles.mirror_hazard_tiles")
def mirror_hazard_tiles() -> dict[str, Any]:
    """Mirror hazard tiles if the GGIS model version changed; otherwise no-op."""
    remote = fetch_model_version()
    local = current_hazard_version()
    if remote == local:
        return {"status": "up_to_date", "hazard_version": local}

    try:
        cog = harvest_hazard_cog(remote)
    except HazardCoverageUnavailable as exc:
        log.warning("hazard mirror blocked for %s: %s", remote, exc)
        return {
            "status": "blocked",
            "hazard_version": local,
            "remote_version": remote,
            "reason": str(exc),
        }
    if not cog.is_file() or cog.stat().st_size == 0:
        raise RuntimeError(f"hazard mirror did not produce a readable COG: {cog}")
    # Use the GGIS model_version verbatim as our hazard layer version, then sweep.
    with connect() as conn:
        set_version(conn, "hazard", remote, source="GGIS Flood Watch", notes=str(cog))
        invalidated = sweep_stale_scores(conn, "hazard", remote)

    summary = {
        "status": "mirrored",
        "hazard_version": remote,
        "previous": local,
        "cog": str(cog),
        "scores_invalidated": invalidated,
    }
    log.info("mirror_hazard_tiles complete: %s", summary)
    return summary

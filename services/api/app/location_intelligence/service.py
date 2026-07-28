"""Scorecard orchestration.

Phase 1 status per domain (Tier discipline, Overview §4):
  * flood        — LIVE via GGIS Flood Watch (Tier 1, wired now).
  * accessibility / amenities / feasibility — Tier 1, pipelines land as OSM/DEM
    ETL completes; returned as `pending` until their layers are published.
  * security / tenure / market / livability — Tier 2–3, later phases.

No domain is surfaced without a defined pipeline behind it: domains without a
live pipeline return status="pending" rather than a fabricated score.
"""
from __future__ import annotations

from app.flood.client import FloodStatus, GGISFloodClient, get_flood_client
from app.location_intelligence.schemas import (
    AnalyzeRequest,
    DomainResult,
    LocationInfo,
    ScorecardResponse,
)
from app.scoring.engine import DomainScore

# Domains whose Tier-1 pipelines are not yet published in this build.
_PENDING_TIER1 = ("amenities", "accessibility", "feasibility")
# Tier 2–3 domains (community/market/security/tenure) — later phases.
_PENDING_LATER = ("security", "tenure", "market", "livability")


def _geohash8(lon: float, lat: float) -> str:
    """Minimal geohash (precision 8) for cache keys — replace with `python-geohash` in ETL."""
    _base32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    bits, bit, ch, even, out = [16, 8, 4, 2, 1], 0, 0, True, []
    while len(out) < 8:
        if even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                ch |= bits[bit]
                lon_range[0] = mid
            else:
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                ch |= bits[bit]
                lat_range[0] = mid
            else:
                lat_range[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            out.append(_base32[ch])
            bit = 0
            ch = 0
    return "".join(out)


def _point_of(req: AnalyzeRequest) -> tuple[float, float]:
    g = req.geometry
    if g.type == "Point":
        return float(g.coordinates[0]), float(g.coordinates[1])
    # Polygon: use the first ring's centroid-ish first vertex for Phase 1 keying.
    ring = g.coordinates[0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return sum(lons) / len(lons), sum(lats) / len(lats)


async def analyze(req: AnalyzeRequest, flood: GGISFloodClient | None = None) -> ScorecardResponse:
    flood = flood or get_flood_client()
    lon, lat = _point_of(req)
    gh8 = _geohash8(lon, lat)

    domains: dict[str, DomainResult] = {}
    layer_versions: dict[str, str] = {}

    # --- Flood (live GGIS call, Tier 1) ---
    fr = await flood.risk(req.geometry.model_dump())
    if fr.normalised is not None:
        flood_score = round(100 * fr.normalised, 1)
        domains["flood"] = DomainResult(
            score=flood_score,
            confidence=fr.confidence or "Medium",
            status="degraded" if fr.status is FloodStatus.DEGRADED else "ok",
            evidence={
                "risk_class": fr.risk_class,
                "model_version": fr.model_version,
                "data_currency": fr.data_currency,
                **fr.factors,
            },
            note=fr.message,
        )
        if fr.model_version:
            layer_versions["hazard"] = fr.model_version
    else:
        domains["flood"] = DomainResult(
            score=None,
            confidence="Low",
            status="degraded",
            note=fr.message or "Flood domain temporarily unavailable",
        )

    # --- Tier-1 domains awaiting their published ETL layers ---
    for d in _PENDING_TIER1:
        domains[d] = DomainResult(
            score=None, confidence="Low", status="pending",
            note="Pipeline scheduled — OSM/DEM ETL in progress (Phase 1).",
        )

    # --- Tier 2–3 domains (later phases) ---
    for d in _PENDING_LATER:
        domains[d] = DomainResult(
            score=None, confidence="Low", status="pending",
            note="Ships in a later phase (Tier 2–3).",
        )

    return ScorecardResponse(
        location=LocationInfo(geohash8=gh8),
        domains=domains,
        layer_versions=layer_versions,
        scoring_profile=req.profile,
        cached=False,
    )


def domainscore_to_result(ds: DomainScore, status: str = "ok") -> DomainResult:
    return DomainResult(
        score=ds.score, confidence=ds.confidence, status=status,  # type: ignore[arg-type]
        evidence=ds.indicators, note=ds.note,
    )

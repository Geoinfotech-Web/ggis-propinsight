"""Scorecard orchestration.

Phase 1 status per domain (Tier discipline, Overview §4):
  * flood        — LIVE via GGIS Flood Watch (risk + factors + last_event + history).
  * amenities    — LIVE when `poi` layer is published (PostGIS KNN + fct-v1).
  * accessibility — LIVE when roads/poi published; landmark time proxies always when scoring.
  * feasibility  — LIVE when `dem` published (DEM samples + flood + utilities).
  * security / tenure / market / livability — Tier 2–3, later phases.

No domain is surfaced without a defined pipeline behind it: domains without a
live pipeline return status="pending" rather than a fabricated score.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.flood.client import FloodStatus, GGISFloodClient, get_flood_client
from app.location_intelligence.accessibility import (
    nearest_road_distance_m,
    score_accessibility,
)
from app.location_intelligence.amenities import (
    nearest_pois,
    pois_within_radius,
    score_amenities,
)
from app.location_intelligence.feasibility import (
    nearest_dem_sample,
    nearest_utility_distance_m,
    score_feasibility,
)
from app.location_intelligence.personas import (
    domain_priority,
    filter_domains_for_persona,
    fit_score,
    persona_public,
    resolve_persona_key,
)
from app.location_intelligence.readiness import (
    LATER_DOMAINS,
    TIER1_REQUIRED_LAYERS,
    layers_ready,
    pending_note,
)
from app.location_intelligence.schemas import (
    AnalyzeRequest,
    DomainResult,
    LocationInfo,
    PersonaInfo,
    ScorecardResponse,
)
from app.scoring.engine import DomainScore

if TYPE_CHECKING:
    from app.cache import ScorecardCache


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
    ring = g.coordinates[0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return sum(lons) / len(lons), sum(lats) / len(lats)


def domainscore_to_result(ds: DomainScore, status: str = "ok") -> DomainResult:
    return DomainResult(
        score=ds.score,
        confidence=ds.confidence,
        status=status,  # type: ignore[arg-type]
        evidence=ds.indicators,
        note=ds.note,
    )


def _pending(domain: str, versions: dict[str, str]) -> DomainResult:
    return DomainResult(
        score=None,
        confidence="Low",
        status="pending",
        note=pending_note(domain, versions),
    )


def _flood_evidence(fr: Any) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "risk_class": fr.risk_class,
        "risk_score": fr.risk_score,
        "model_version": fr.model_version,
        "data_currency": fr.data_currency,
        **(fr.factors or {}),
    }
    if fr.last_event:
        evidence["last_event"] = fr.last_event
    if fr.history_events:
        evidence["history_events"] = fr.history_events[:5]
    return evidence


async def _score_amenities(
    session: AsyncSession | None, lon: float, lat: float, versions: dict[str, str]
) -> DomainResult:
    required = TIER1_REQUIRED_LAYERS["amenities"]
    if not layers_ready(versions, required) or session is None:
        return _pending("amenities", versions)
    nearest = await nearest_pois(session, lon, lat)
    if all(v is None for v in nearest.values()):
        return DomainResult(
            score=None,
            confidence="Low",
            status="degraded",
            evidence={},
            note="POI layer published but no amenities found near this location.",
        )
    result = domainscore_to_result(score_amenities(nearest), status="ok")
    nearby = await pois_within_radius(session, lon, lat)
    if nearby:
        result.evidence["nearby"] = nearby
    return result


async def _score_accessibility(
    session: AsyncSession | None, lon: float, lat: float, versions: dict[str, str]
) -> DomainResult:
    required = TIER1_REQUIRED_LAYERS["accessibility"]
    if not layers_ready(versions, required) or session is None:
        return _pending("accessibility", versions)
    road_m = await nearest_road_distance_m(session, lon, lat)
    return domainscore_to_result(
        score_accessibility(road_m, lon=lon, lat=lat),
        status="ok",
    )


async def _score_feasibility(
    session: AsyncSession | None,
    lon: float,
    lat: float,
    versions: dict[str, str],
    flood_normalised: float | None,
) -> DomainResult:
    required = TIER1_REQUIRED_LAYERS["feasibility"]
    if not layers_ready(versions, required) or session is None:
        return _pending("feasibility", versions)
    dem = await nearest_dem_sample(session, lon, lat)
    if dem is None:
        return DomainResult(
            score=None,
            confidence="Low",
            status="degraded",
            evidence={},
            note="DEM layer published but no terrain samples near this location.",
        )
    util = await nearest_utility_distance_m(session, lon, lat)
    return domainscore_to_result(
        score_feasibility(
            slope_deg=dem["slope_deg"],
            flood_normalised=flood_normalised,
            utility_distance_m=util,
            twi=dem["twi"],
        ),
        status="ok",
    )


async def analyze(
    req: AnalyzeRequest,
    flood: GGISFloodClient | None = None,
    versions: dict[str, str] | None = None,
    cache: ScorecardCache | None = None,
    session: AsyncSession | None = None,
) -> ScorecardResponse:
    """Compute (or serve from cache) the eight-domain scorecard."""
    flood = flood or get_flood_client()
    lon, lat = _point_of(req)
    gh8 = _geohash8(lon, lat)
    versions = versions or {}
    persona_key = resolve_persona_key(req.profile)

    cache_key = None
    if cache is not None:
        cache_key = cache.make_key(persona_key, gh8, versions)
        hit = await cache.get(cache_key)
        if hit is not None:
            hit["cached"] = True
            return ScorecardResponse.model_validate(hit)

    domains: dict[str, DomainResult] = {}
    layer_versions: dict[str, str] = dict(versions)

    # --- Flood (live GGIS call, Tier 1) ---
    fr = await flood.risk(req.geometry.model_dump())
    if hasattr(flood, "history") and fr.status is FloodStatus.OK:
        try:
            fr.history_events = await flood.history(lon, lat)
        except Exception:  # noqa: BLE001 — history is enrichment, never fail analyze
            fr.history_events = []

    if fr.normalised is not None:
        flood_score = round(100 * fr.normalised, 1)
        domains["flood"] = DomainResult(
            score=flood_score,
            confidence=fr.confidence or "Medium",
            status="degraded" if fr.status is FloodStatus.DEGRADED else "ok",
            evidence=_flood_evidence(fr),
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

    # --- Tier-1 domains gated by published ETL layers ---
    domains["amenities"] = await _score_amenities(session, lon, lat, versions)
    domains["accessibility"] = await _score_accessibility(session, lon, lat, versions)
    domains["feasibility"] = await _score_feasibility(
        session, lon, lat, versions, fr.normalised
    )

    for d in LATER_DOMAINS:
        domains[d] = _pending(d, versions)

    priority = domain_priority(persona_key)
    # Drop domains not in this persona's Location Report (e.g. feasibility for buyers).
    report_domains = filter_domains_for_persona(domains, persona_key)
    response = ScorecardResponse(
        location=LocationInfo(geohash8=gh8),
        domains=report_domains,
        layer_versions=layer_versions,
        scoring_profile=persona_key,
        cached=False,
        persona=PersonaInfo(**persona_public(persona_key)),
        fit_score=fit_score(report_domains, persona_key),
        domain_priority=priority,
    )

    if cache is not None and cache_key is not None:
        await cache.set(cache_key, response.model_dump())

    return response

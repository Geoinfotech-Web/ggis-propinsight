"""Scorecard orchestration.

Phase 1 status per domain (Tier discipline, Overview §4):
  * flood        — LIVE via GGIS Flood Watch (risk + factors + last_event + history).
  * amenities    — LIVE when `poi` layer is published (PostGIS KNN + fct-v1).
  * accessibility — LIVE when roads/poi published; landmark time proxies always when scoring.
  * feasibility  — LIVE when `dem` published (DEM samples + flood + utilities).
  * security     — LIVE when `security` published (district incident aggregate + police).
  * tenure       — LIVE when `planning` published (advisory planning-overlay screen).
  * market       — LIVE when geocoded partner samples publish the `market` layer.
  * livability   — LIVE when land-cover and surface-heat layers are published.

No domain is surfaced without a defined pipeline behind it: domains without a
live pipeline return status="pending" rather than a fabricated score.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.flood.client import (
    FloodStatus,
    GGISFloodClient,
    get_flood_client,
    validated_risk_score,
)
from app.location_intelligence.accessibility import (
    nearest_road_distance_m,
    score_accessibility,
)
from app.location_intelligence.amenities import (
    nearest_pois,
    pois_within_radius,
    score_amenities,
)
from app.location_intelligence.development_outlook import (
    PROFESSIONAL_PERSONAS,
)
from app.location_intelligence.development_outlook import (
    development_outlook as build_development_outlook,
)
from app.location_intelligence.feasibility import (
    MIN_AVAILABLE_WEIGHT,
    available_weight,
    nearest_mapped_watercourse,
    nearest_modelled_drainage,
    nearest_utility_distance_m,
    nearest_utility_services,
    score_feasibility,
    terrain_profile,
)
from app.location_intelligence.land_cover import land_cover_at_point
from app.location_intelligence.land_use import land_use_at_point
from app.location_intelligence.livability import (
    environmental_context,
    livability_rating,
    score_livability,
)
from app.location_intelligence.market import market_samples_for_point, score_market
from app.location_intelligence.network_coverage import (
    EnextNetworkCoverageClient,
    get_network_coverage_client,
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
    REQUIRED_LAYERS,
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
from app.location_intelligence.security import (
    district_for_point,
    incidents_for_location,
    nearest_police_distance_m,
    score_security,
    ward_for_point,
)
from app.location_intelligence.summary import build_highlights, build_summary
from app.location_intelligence.tenure import overlapping_planning, score_tenure
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
        included_in_fit=ds.score is not None,
        evidence=ds.indicators,
        note=ds.note,
    )


def _pending(domain: str, versions: dict[str, str]) -> DomainResult:
    return DomainResult(
        score=None,
        confidence="Low",
        status="pending",
        included_in_fit=False,
        note=pending_note(domain, versions),
    )


def _flood_evidence(fr: Any) -> dict[str, Any]:
    public_factors = {
        key: value
        for key, value in (fr.factors or {}).items()
        if key != "hazard_index_eligible"
    }
    evidence: dict[str, Any] = {
        "risk_class": fr.risk_class,
        "data_mode": getattr(fr, "data_mode", "live"),
        "model_version": fr.model_version,
        "data_currency": fr.data_currency,
        **public_factors,
    }
    if fr.last_event:
        evidence["last_event"] = fr.last_event
    if fr.history_events:
        evidence["history_events"] = fr.history_events[:5]
    return evidence


CLASS_DERIVED_HAZARD: dict[str, float] = {
    "very low": 0.10,
    "low": 0.25,
    "moderate": 0.50,
    "high": 0.75,
    "very high": 0.90,
    "highly susceptible": 0.90,
}


def _class_derived_hazard(fr: Any) -> float | None:
    """Map the live GGIS susceptibility class to a transparent ordinal index."""
    factors = fr.factors if isinstance(fr.factors, dict) else {}
    if factors.get("hazard_index_eligible") is not True:
        return None
    if not isinstance(fr.risk_class, str):
        return None
    return CLASS_DERIVED_HAZARD.get(fr.risk_class.strip().lower())


def _flood_rating(risk_class: Any) -> str | None:
    if not isinstance(risk_class, str) or not risk_class.strip():
        return None
    return f"{risk_class.strip()} flood risk"


async def _score_amenities(
    session: AsyncSession | None,
    lon: float,
    lat: float,
    versions: dict[str, str],
    radius_m: int,
) -> DomainResult:
    required = REQUIRED_LAYERS["amenities"]
    if not layers_ready(versions, required) or session is None:
        return _pending("amenities", versions)
    nearest = await nearest_pois(session, lon, lat, radius_m=radius_m)
    if all(v is None for v in nearest.values()):
        return DomainResult(
            score=None,
            confidence="Low",
            status="degraded",
            included_in_fit=False,
            evidence={},
            note="POI layer published but no amenities found near this location.",
        )
    result = domainscore_to_result(score_amenities(nearest), status="ok")
    nearby = await pois_within_radius(session, lon, lat, radius_m=radius_m)
    if nearby:
        result.evidence["nearby"] = nearby
        result.evidence["nearby_counts"] = {
            item["category"]: item["total_count"] for item in nearby
        }
    result.evidence["coverage_radius_m"] = radius_m
    return result


async def _score_accessibility(
    session: AsyncSession | None, lon: float, lat: float, versions: dict[str, str]
) -> DomainResult:
    required = REQUIRED_LAYERS["accessibility"]
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
    required = REQUIRED_LAYERS["feasibility"]
    if not layers_ready(versions, required) or session is None:
        return _pending("feasibility", versions)
    profile = await terrain_profile(session, lon, lat)
    if profile is None:
        return DomainResult(
            score=None,
            confidence="Low",
            status="degraded",
            included_in_fit=False,
            evidence={},
            note="DEM layer published but no terrain profile covers this one-kilometre site.",
        )
    util = await nearest_utility_distance_m(session, lon, lat)
    coverage = available_weight(
        terrain=True,
        flood=flood_normalised is not None,
        utility=util is not None,
        wetness=profile.get("twi_p90") is not None,
    )
    services = await nearest_utility_services(session, lon, lat)
    evidence = {
        "terrain": profile,
        "drainage": {
            "modelled": await nearest_modelled_drainage(session, lon, lat),
            "mapped_watercourse": await nearest_mapped_watercourse(session, lon, lat),
            "advisory": "Modelled and openly mapped drainage are not surveyed site drainage.",
        },
        "servicing": {
            **services,
            "nearest_road": (
                None
                if (road_m := await nearest_road_distance_m(session, lon, lat)) is None
                else {
                    "distance_m": round(road_m, 1),
                    "kind": "mapped road centreline",
                    "source": "Published roads layer",
                }
            ),
        },
        "available_weight_pct": round(coverage * 100),
    }
    if coverage < MIN_AVAILABLE_WEIGHT:
        return DomainResult(
            score=None,
            confidence="Low",
            status="degraded",
            included_in_fit=False,
            evidence=evidence,
            note=(
                "Detailed terrain evidence is available, but fewer than 60% of "
                "weighted feasibility inputs are live, so no score is reported."
            ),
        )
    ds = score_feasibility(
        buildable_share_pct=profile["buildable_share_pct"],
        flood_normalised=flood_normalised,
        utility_distance_m=util,
        twi=profile["twi_p90"],
    )
    result = domainscore_to_result(ds, status="ok")
    result.evidence.update(evidence)
    result.note = "Physical buildability from a fixed 1 km terrain context and servicing proxies."
    return result


async def _score_livability(
    session: AsyncSession | None,
    lon: float,
    lat: float,
    versions: dict[str, str],
) -> DomainResult:
    required = REQUIRED_LAYERS["livability"]
    if not layers_ready(versions, required) or session is None:
        return _pending("livability", versions)
    context = await environmental_context(session, lon, lat)
    if context is None or any(
        context.get(key) is None
        for key in ("green_share", "heat_percentile", "built_bare_share")
    ):
        return DomainResult(
            score=None,
            confidence="Low",
            status="degraded",
            included_in_fit=False,
            evidence=context or {},
            note="Published land-cover and surface-heat layers do not both cover this site.",
        )
    ds = score_livability(
        green_share=context["green_share"],
        heat_percentile=context["heat_percentile"],
        built_bare_share=context["built_bare_share"],
        evidence={
            "surface_temperature": {
                "value": round(context["surface_temp_c"], 1)
                if context.get("surface_temp_c") is not None
                else None,
                "unit": "°C surface temperature",
                "fct_percentile": round(context["heat_percentile"] * 100, 1),
            },
            "context_radius_m": context["context_radius_m"],
            "data_period": context.get("data_period"),
        },
    )
    result = domainscore_to_result(ds, status="ok")
    result.rating = livability_rating(result.score)
    return result


async def _score_security(
    session: AsyncSession | None,
    lon: float,
    lat: float,
    versions: dict[str, str],
    district: dict[str, Any] | None,
    ward: dict[str, Any] | None,
    radius_m: int,
) -> DomainResult:
    required = REQUIRED_LAYERS["security"]
    if not layers_ready(versions, required) or session is None:
        return _pending("security", versions)
    nearby_police = await pois_within_radius(
        session,
        lon,
        lat,
        categories=("police",),
        radius_m=radius_m,
    )
    # Incident totals require at least the district fallback; local police POIs
    # remain useful but are not enough to imply a local incident rate.
    if district is None:
        result = DomainResult(
            score=None,
            confidence="Low",
            status="degraded",
            included_in_fit=False,
            evidence={},
            note="No published incident aggregate covers this point.",
        )
        if nearby_police:
            result.evidence["nearby"] = nearby_police
            result.evidence["nearby_count"] = nearby_police[0]["total_count"]
        result.evidence["coverage_radius_m"] = radius_m
        return result
    incidents = await incidents_for_location(
        session,
        district["id"],
        ward["id"] if ward else None,
    )
    police_m = await nearest_police_distance_m(
        session,
        lon,
        lat,
        radius_m=radius_m,
    )
    ds = score_security(
        incident_total=None if incidents is None else incidents["total"],
        police_distance_m=police_m,
        period=None if incidents is None else incidents["period"],
        by_category=None if incidents is None else incidents["by_category"],
        district=district["name"],
        ward=ward["name"] if ward else None,
        aggregation_level=(
            "district" if incidents is None else incidents["aggregation_level"]
        ),
        incident_source=None if incidents is None else incidents.get("source"),
    )
    result = domainscore_to_result(ds, status="ok")
    if nearby_police:
        result.evidence["nearby"] = nearby_police
        result.evidence["nearby_count"] = nearby_police[0]["total_count"]
    result.evidence["coverage_radius_m"] = radius_m
    return result


async def _score_tenure(
    session: AsyncSession | None, lon: float, lat: float, versions: dict[str, str]
) -> DomainResult:
    required = REQUIRED_LAYERS["tenure"]
    if not layers_ready(versions, required) or session is None:
        return _pending("tenure", versions)
    overlays = await overlapping_planning(session, lon, lat)
    return domainscore_to_result(score_tenure(overlays), status="ok")


async def _score_market(
    session: AsyncSession | None,
    lon: float,
    lat: float,
    versions: dict[str, str],
    persona: str,
    radius_m: int,
) -> DomainResult:
    required = REQUIRED_LAYERS["market"]
    if not layers_ready(versions, required) or session is None:
        return _pending("market", versions)
    samples, baselines = await market_samples_for_point(
        session,
        lon,
        lat,
        radius_m=radius_m,
    )
    ds = score_market(samples, baselines, persona=persona, radius_m=radius_m)
    return domainscore_to_result(ds, status="ok" if ds.score is not None else "degraded")


async def analyze(
    req: AnalyzeRequest,
    flood: GGISFloodClient | None = None,
    network_coverage: EnextNetworkCoverageClient | None = None,
    versions: dict[str, str] | None = None,
    cache: ScorecardCache | None = None,
    session: AsyncSession | None = None,
) -> ScorecardResponse:
    """Compute (or serve from cache) the eight-domain scorecard."""
    flood = flood or get_flood_client()
    lon, lat = _point_of(req)
    network_coverage = network_coverage or get_network_coverage_client()
    gh8 = _geohash8(lon, lat)
    versions = versions or {}
    persona_key = resolve_persona_key(req.profile)
    radius_m = req.radius_m
    flood_data_mode = str(getattr(flood, "data_mode", "live"))

    layer_versions: dict[str, str] = dict(versions)
    cache_key = None
    # Resolve the live GGIS model before trusting a cached flood result. The
    # registry's hazard mirror may legitimately lag the live risk service.
    if cache is not None and hasattr(flood, "meta"):
        try:
            meta = await flood.meta()
            live_model = meta.get("model_version") if isinstance(meta, dict) else None
        except Exception:  # noqa: BLE001 - risk() still provides graceful degradation
            live_model = None
        if live_model:
            layer_versions["hazard"] = str(live_model)
            cache_key = cache.make_key(
                persona_key, gh8, layer_versions, radius_m, flood_data_mode
            )
            hit = await cache.get(cache_key)
            if hit is not None:
                hit["cached"] = True
                return ScorecardResponse.model_validate(hit)

    domains: dict[str, DomainResult] = {}

    # --- Flood (live GGIS call, Tier 1) ---
    fr = await flood.risk(req.geometry.model_dump())
    flood_data_mode = str(getattr(fr, "data_mode", flood_data_mode))
    if fr.model_version:
        layer_versions["hazard"] = fr.model_version

    # If meta was unavailable or raced a model deployment, use the version from
    # the risk response and try the correctly-versioned cache before DB scoring.
    if (
        cache is not None
        and fr.status is FloodStatus.OK
        and fr.model_version
    ):
        resolved_key = cache.make_key(
            persona_key, gh8, layer_versions, radius_m, flood_data_mode
        )
        if resolved_key != cache_key:
            hit = await cache.get(resolved_key)
            if hit is not None:
                hit["cached"] = True
                return ScorecardResponse.model_validate(hit)
        cache_key = resolved_key
    elif fr.status is not FloodStatus.OK:
        # Do not retain degraded/unavailable flood responses for the normal 24h TTL.
        cache_key = None

    if hasattr(flood, "history") and fr.status is FloodStatus.OK:
        try:
            fr.history_events = await flood.history(lon, lat)
        except Exception:  # noqa: BLE001 — history is enrichment, never fail analyze
            fr.history_events = []

    upstream_hazard_fraction = validated_risk_score(fr.risk_score)
    derived_hazard_fraction = (
        _class_derived_hazard(fr) if upstream_hazard_fraction is None else None
    )
    hazard_fraction = (
        upstream_hazard_fraction
        if upstream_hazard_fraction is not None
        else derived_hazard_fraction
    )
    hazard_is_class_derived = (
        upstream_hazard_fraction is None and derived_hazard_fraction is not None
    )
    flood_is_demo = flood_data_mode == "mock"
    flood_included_in_fit = (
        fr.status is FloodStatus.OK and not flood_is_demo and hazard_fraction is not None
    )
    flood_suitability_fraction = (
        1.0 - hazard_fraction if flood_included_in_fit and hazard_fraction is not None else None
    )
    flood_rating = _flood_rating(fr.risk_class)
    if hazard_fraction is not None:
        fr.factors["hazard_index"] = round(100 * hazard_fraction, 1)

    if hazard_fraction is not None:
        flood_score = round(100 * hazard_fraction, 1)
        flood_status = (
            "demo"
            if flood_is_demo
            else "degraded"
            if fr.status is FloodStatus.DEGRADED
            else "ok"
        )
        flood_note = fr.message
        if hazard_is_class_derived:
            flood_note = (
                "Based on the live GGIS flood susceptibility for this location. "
                "Lower hazard values are safer."
            )
        if flood_is_demo:
            flood_note = "Demo flood data—do not rely on this result for a property decision."
        domains["flood"] = DomainResult(
            score=flood_score,
            confidence=fr.confidence or "Medium",
            status=flood_status,
            score_direction="higher_is_worse",
            rating=flood_rating,
            included_in_fit=flood_included_in_fit,
            evidence=_flood_evidence(fr),
            note=flood_note,
        )
    else:
        flood_note = fr.message or "Flood hazard score is unavailable or invalid."
        if flood_is_demo:
            flood_note = "Demo flood data is unavailable and is not used in this report."
        domains["flood"] = DomainResult(
            score=None,
            confidence="Low",
            status="demo" if flood_is_demo else "degraded",
            score_direction="higher_is_worse",
            rating=flood_rating,
            included_in_fit=False,
            evidence=_flood_evidence(fr),
            note=flood_note,
        )

    # --- Resolve administrative context once (drives security + LocationInfo) ---
    district = await district_for_point(session, lon, lat) if session is not None else None
    ward = await ward_for_point(session, lon, lat) if session is not None else None
    land_use = await land_use_at_point(session, lon, lat) if session is not None else None
    land_cover = await land_cover_at_point(session, lon, lat) if session is not None else None
    if land_use and land_use["designation"] == "official_masterplan":
        planning_status = "official"
    elif land_use:
        planning_status = "mapped_reference"
    elif land_cover:
        planning_status = "observed_cover_only"
    else:
        planning_status = "unmapped"

    # --- Tier-1 domains gated by published ETL layers ---
    domains["amenities"] = await _score_amenities(
        session,
        lon,
        lat,
        versions,
        radius_m,
    )
    domains["accessibility"] = await _score_accessibility(session, lon, lat, versions)
    domains["feasibility"] = await _score_feasibility(
        session, lon, lat, versions, flood_suitability_fraction
    )
    domains["livability"] = await _score_livability(session, lon, lat, versions)

    # --- Tier 2 domains (most-local safe security aggregate, planning overlay) ---
    domains["security"] = await _score_security(
        session, lon, lat, versions, district, ward, radius_m
    )
    domains["tenure"] = await _score_tenure(session, lon, lat, versions)
    domains["market"] = await _score_market(
        session,
        lon,
        lat,
        versions,
        persona_key,
        radius_m,
    )
    try:
        coverage = await network_coverage.lookup(lon, lat)
    except Exception:  # noqa: BLE001 - evidence enrichment must never fail analyze
        coverage = {
            "providers": [],
            "providers_checked": 0,
            "providers_with_5g": [],
            "providers_with_4g": [],
            "available_count": 0,
            "available_counts": {"4G": 0, "5G": 0},
            "connectivity_read": "Coverage unavailable",
            "source": "Enext Wireless EMetrics",
            "source_url": "https://metrics.enextwireless.com/",
            "checked_at": None,
        }
    # Fold mobile/5G evidence under Internet/ISP amenity details (not a separate block).
    if "amenities" in domains:
        isp_raw = domains["amenities"].evidence.get("isp")
        if isinstance(isp_raw, dict):
            domains["amenities"].evidence["isp"] = {
                **isp_raw,
                "network_coverage": coverage,
                "connectivity_read": coverage["connectivity_read"],
            }
        elif isp_raw is None:
            domains["amenities"].evidence["isp"] = {
                "network_coverage": coverage,
                "connectivity_read": coverage["connectivity_read"],
            }
        else:
            domains["amenities"].evidence["isp"] = {
                "value": isp_raw,
                "network_coverage": coverage,
                "connectivity_read": coverage["connectivity_read"],
            }

    for d in LATER_DOMAINS:
        domains[d] = _pending(d, versions)

    priority = domain_priority(persona_key)
    # Drop domains not in this persona's Location Report (e.g. feasibility for buyers).
    report_domains = filter_domains_for_persona(domains, persona_key)
    persona_meta = persona_public(persona_key)
    fit = fit_score(report_domains, persona_key)
    outlook = None
    if persona_key in PROFESSIONAL_PERSONAS and session is not None:
        outlook = await build_development_outlook(
            session,
            lon,
            lat,
            radius_m,
            ward=ward["name"] if ward else None,
            area_council=ward["area_council"] if ward else None,
        )

    response = ScorecardResponse(
        location=LocationInfo(
            geohash8=gh8,
            district=district["name"] if district else None,
            ward=ward["name"] if ward else None,
            area_council=ward["area_council"] if ward else None,
            state=district["state"] if district else None,
            land_use=land_use,
            land_cover=land_cover,
            planning_status=planning_status,
        ),
        domains=report_domains,
        analysis_radius_m=radius_m,
        layer_versions=layer_versions,
        scoring_profile=persona_key,
        cached=False,
        persona=PersonaInfo(**persona_meta),
        fit_score=fit,
        summary=build_summary(
            persona_key,
            persona_meta["label"],
            fit,
            report_domains,
        ),
        highlights=build_highlights(persona_key, report_domains, priority),
        domain_priority=priority,
        development_outlook=outlook,
    )

    if cache is not None and cache_key is not None:
        await cache.set(cache_key, response.model_dump())

    return response

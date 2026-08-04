"""Phase 1 domain → layer readiness map (TDD §4.6).

Product rule: no domain is scored until its required layers are published in
`layer_registry`. This module is the single source of truth for that dependency
graph so ETL scheduling, API pending notes, and ops docs stay aligned.
"""
from __future__ import annotations

from dataclasses import dataclass

UNPUBLISHED = "unpublished"


@dataclass(frozen=True)
class DomainDependency:
    domain: str
    tier: int
    required_layers: tuple[str, ...]
    pipeline_tasks: tuple[str, ...]
    phase: str
    note: str


# Ordered by Phase 1 unlock priority, then later tiers.
DOMAIN_DEPENDENCIES: tuple[DomainDependency, ...] = (
    DomainDependency(
        domain="flood",
        tier=1,
        required_layers=("hazard",),  # live GGIS; hazard mirror is resilience, not a hard gate
        pipeline_tasks=("aia_etl.tasks.flood_tiles.mirror_hazard_tiles",),
        phase="1",
        note="Live via GGIS Flood Watch; mirror hazard COGs for map resilience.",
    ),
    DomainDependency(
        domain="amenities",
        tier=1,
        required_layers=("poi",),
        pipeline_tasks=("aia_etl.tasks.amenities.refresh_amenities",),
        phase="1",
        note="Needs published OSM/agency POIs; scored via PostGIS KNN + fct-v1 weights.",
    ),
    DomainDependency(
        domain="accessibility",
        tier=1,
        required_layers=("roads", "poi"),
        pipeline_tasks=(
            "aia_etl.tasks.osm.refresh_osm",
            "aia_etl.tasks.amenities.refresh_amenities",
        ),
        phase="1",
        note="Needs roads (+ POIs for destinations) and OSRM/Valhalla routing graph.",
    ),
    DomainDependency(
        domain="feasibility",
        tier=1,
        required_layers=("dem",),
        pipeline_tasks=(
            "aia_etl.tasks.dem.dem_from_gee",
            "aia_etl.tasks.dem.terrain_derivatives",
        ),
        phase="1",
        note="Needs DEM slope / flow-accumulation / TWI COGs (GEE IAM may block).",
    ),
    DomainDependency(
        domain="security",
        tier=2,
        required_layers=("security",),
        pipeline_tasks=(),
        phase="2",
        note="District-level incident aggregate + police proximity (no address-level).",
    ),
    DomainDependency(
        domain="tenure",
        tier=2,
        required_layers=("planning",),
        pipeline_tasks=(),
        phase="2",
        note="Advisory planning overlays (acquisition / layout / setback).",
    ),
    DomainDependency(
        domain="market",
        tier=3,
        required_layers=("market",),
        pipeline_tasks=("aia_etl.tasks.market.refresh_market_samples",),
        phase="3",
        note="Geocoded listing/transaction samples from the partner-agent network.",
    ),
    DomainDependency(
        domain="livability",
        tier=3,
        required_layers=(),
        pipeline_tasks=(),
        phase="3",
        note="Community reviews + density — later phase.",
    ),
)

# Phase 1 ETL run order for ops (publish blocking layers first).
PHASE1_PIPELINE_PRIORITY: tuple[str, ...] = (
    "aia_etl.tasks.osm.refresh_osm",           # unlocks amenities + accessibility data
    "aia_etl.tasks.amenities.refresh_amenities",  # multi-source named POIs
    "aia_etl.tasks.dem.dem_from_gee",          # unlocks feasibility terrain inputs
    "aia_etl.tasks.flood_tiles.mirror_hazard_tiles",  # map resilience if GGIS downs
)


def dependency_for(domain: str) -> DomainDependency | None:
    for dep in DOMAIN_DEPENDENCIES:
        if dep.domain == domain:
            return dep
    return None


def layers_ready(required: tuple[str, ...], published: dict[str, str]) -> bool:
    """True when every required layer is present and not `unpublished`."""
    if not required:
        return False
    for layer in required:
        version = published.get(layer)
        if version is None or version == UNPUBLISHED:
            return False
    return True


def pending_note(domain: str, published: dict[str, str] | None = None) -> str:
    """Human-readable pending reason for the scorecard."""
    dep = dependency_for(domain)
    if dep is None:
        return "Unknown domain."
    published = published or {}
    # Domains with no required layers are not yet wired (later phase).
    if not dep.required_layers:
        return f"Ships in a later phase (Tier {dep.tier})."
    missing = [
        layer
        for layer in dep.required_layers
        if published.get(layer) in (None, UNPUBLISHED)
    ]
    if missing:
        return (
            f"Pipeline scheduled — waiting on published layer(s): {', '.join(missing)} "
            f"(Phase {dep.phase})."
        )
    return dep.note


def readiness_snapshot(published: dict[str, str]) -> list[dict[str, object]]:
    """Serializable readiness matrix for ops / meta endpoints."""
    rows: list[dict[str, object]] = []
    for dep in DOMAIN_DEPENDENCIES:
        # Flood is live via GGIS regardless of hazard mirror publish state.
        if dep.domain == "flood":
            ready = True
        else:
            ready = layers_ready(dep.required_layers, published) if dep.required_layers else False
        rows.append(
            {
                "domain": dep.domain,
                "tier": dep.tier,
                "phase": dep.phase,
                "required_layers": list(dep.required_layers),
                "ready": ready,
                "pipeline_tasks": list(dep.pipeline_tasks),
                "note": pending_note(dep.domain, published) if not ready else dep.note,
            }
        )
    return rows

"""Domain → layer readiness gates for the scorecard (mirrors etl/aia_etl/domain_deps).

Kept inside the API package so the gateway does not import the ETL worker code.
Keep the required-layer sets in sync with `aia_etl.domain_deps.DOMAIN_DEPENDENCIES`.
"""
from __future__ import annotations

UNPUBLISHED = "unpublished"

# Domains gated on published layers. Each scores once its layers publish
# (whether from the FCT demo seed or live ETL). Flood is live via GGIS.
REQUIRED_LAYERS: dict[str, tuple[str, ...]] = {
    "amenities": ("poi",),
    "accessibility": ("roads", "poi"),
    "feasibility": ("dem",),
    "security": ("security",),
    "tenure": ("planning",),
    "market": ("market",),
    "livability": ("land_cover", "surface_heat"),
}

# Back-compat alias (Tier-1 subset historically referenced by name).
TIER1_REQUIRED_LAYERS = REQUIRED_LAYERS

# Domains still awaiting a later phase (no scoring wired yet).
LATER_DOMAINS: tuple[str, ...] = ()


def is_published(versions: dict[str, str], layer: str) -> bool:
    version = versions.get(layer)
    return version is not None and version != UNPUBLISHED


def layers_ready(versions: dict[str, str], required: tuple[str, ...]) -> bool:
    return all(is_published(versions, layer) for layer in required)


def pending_note(domain: str, versions: dict[str, str]) -> str:
    if domain in LATER_DOMAINS:
        return "Ships in a later phase (Tier 3)."
    required = REQUIRED_LAYERS.get(domain, ())
    missing = [layer for layer in required if not is_published(versions, layer)]
    if missing:
        return (
            f"Pipeline scheduled - waiting on published layer(s): {', '.join(missing)}."
        )
    return "Layers published - waiting on domain query."


def readiness_rows(versions: dict[str, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "domain": "flood",
            "ready": True,
            "required_layers": ["hazard"],
            "note": "Live via GGIS Flood Watch (risk, factors, last_event, history).",
        }
    ]
    for domain, required in REQUIRED_LAYERS.items():
        ready = layers_ready(versions, required)
        rows.append(
            {
                "domain": domain,
                "ready": ready,
                "required_layers": list(required),
                "note": pending_note(domain, versions) if not ready else "Ready for scoring.",
            }
        )
    for domain in LATER_DOMAINS:
        rows.append(
            {
                "domain": domain,
                "ready": False,
                "required_layers": [],
                "note": pending_note(domain, versions),
            }
        )
    return rows

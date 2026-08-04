"""Target-user personas — domain-level importance weights (PropInsight).

Indicator maths inside each domain stay on fct-v1. Personas change which
domains matter most when computing a fit score and ordering the scorecard.
"""
from __future__ import annotations

from typing import Any

# Domains that appear in every scorecard (Overview §3).
DOMAINS: tuple[str, ...] = (
    "flood",
    "security",
    "amenities",
    "accessibility",
    "tenure",
    "market",
    "livability",
    "feasibility",
)

# Legacy analyze profile → default persona.
LEGACY_PROFILE_MAP: dict[str, str] = {
    "fct-v1": "home_buyer",
}


PERSONAS: dict[str, dict[str, Any]] = {
    "home_buyer": {
        "key": "home_buyer",
        "label": "Home Buyer",
        "blurb": "Family home — flood, schools & clinics, safety, access",
        # Feasibility excluded — not relevant to home acquisition report.
        "domain_weights": {
            "flood": 0.21,
            "amenities": 0.21,
            "security": 0.16,
            "accessibility": 0.16,
            "livability": 0.10,
            "tenure": 0.09,
            "market": 0.07,
        },
        "amenity_order": ("school", "hospital", "market", "bank"),
    },
    "investor": {
        "key": "investor",
        "label": "Investor",
        "blurb": "Yield & risk — market, tenure, security, flood",
        "domain_weights": {
            "market": 0.25,
            "security": 0.15,
            "flood": 0.15,
            "tenure": 0.15,
            "accessibility": 0.10,
            "amenities": 0.08,
            "feasibility": 0.07,
            "livability": 0.05,
        },
        "amenity_order": ("bank", "market", "hospital", "school"),
    },
    "tenant": {
        "key": "tenant",
        "label": "Tenant",
        "blurb": "Day-to-day living — amenities, safety, access, livability",
        # Feasibility excluded — not relevant to rental living report.
        "domain_weights": {
            "amenities": 0.22,
            "security": 0.21,
            "flood": 0.15,
            "accessibility": 0.15,
            "livability": 0.15,
            "market": 0.09,
            "tenure": 0.03,
        },
        "amenity_order": ("school", "hospital", "market", "bank"),
    },
    "developer": {
        "key": "developer",
        "label": "Developer",
        "blurb": "Land / estate — feasibility, tenure, flood, access",
        "domain_weights": {
            "feasibility": 0.23,
            "tenure": 0.20,
            "flood": 0.15,
            "accessibility": 0.12,
            "market": 0.10,
            "security": 0.10,
            "amenities": 0.05,
            "livability": 0.05,
        },
        "amenity_order": ("market", "bank", "hospital", "school"),
    },
}


def resolve_persona_key(profile: str | None) -> str:
    """Map request profile to a known persona key (default home_buyer)."""
    if not profile:
        return "home_buyer"
    if profile in PERSONAS:
        return profile
    return LEGACY_PROFILE_MAP.get(profile, "home_buyer")


def get_persona(profile: str | None) -> dict[str, Any]:
    key = resolve_persona_key(profile)
    return PERSONAS[key]


def included_domains(profile: str | None) -> set[str]:
    """Domains that appear in this persona's Location Report."""
    return set(get_persona(profile)["domain_weights"].keys())


def domain_priority(profile: str | None) -> list[str]:
    """Domains ordered by descending weight for this persona (excluded omitted)."""
    persona = get_persona(profile)
    weights: dict[str, float] = persona["domain_weights"]
    return sorted(
        weights.keys(),
        key=lambda d: (-weights[d], DOMAINS.index(d) if d in DOMAINS else 99),
    )


def filter_domains_for_persona(
    domains: dict[str, Any],
    profile: str | None,
) -> dict[str, Any]:
    """Keep only domains included in the persona's report."""
    allowed = included_domains(profile)
    return {k: v for k, v in domains.items() if k in allowed}


def fit_score(
    domains: dict[str, Any],
    profile: str | None,
) -> float | None:
    """Weighted average of domains with a numeric score; renormalise over present.

    ``domains`` values may be DomainResult-like objects (``.score``) or dicts
    with a ``score`` key.
    """
    weights: dict[str, float] = get_persona(profile)["domain_weights"]
    present: list[tuple[float, float]] = []  # (weight, score 0..100)
    for domain, weight in weights.items():
        result = domains.get(domain)
        if result is None:
            continue
        score = result.score if hasattr(result, "score") else result.get("score")
        if score is None:
            continue
        present.append((float(weight), float(score)))

    if not present:
        return None
    total_w = sum(w for w, _ in present)
    if total_w <= 0:
        return None
    return round(sum(w * s for w, s in present) / total_w, 1)


def persona_public(profile: str | None) -> dict[str, str]:
    p = get_persona(profile)
    return {"key": p["key"], "label": p["label"], "blurb": p["blurb"]}

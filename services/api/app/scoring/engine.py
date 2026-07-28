"""Weighted multi-criteria scoring (TDD §4.4).

    score_d = 100 * Σ_i ( w_i * n_i )       # per domain d
    n_i  = normalised indicator value in [0, 1]
           distance    -> piecewise-linear decay (full ≤ d_min, zero ≥ d_max)
           categorical -> lookup table
           hazard      -> inverted class mapping (handled by the flood client)
    w_i  = domain weight, Σ w_i = 1
    confidence_d = f(recency, resolution, verification) -> {High, Medium, Low}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Indicator:
    key: str
    value: float | None            # normalised [0,1]; None -> missing/unavailable
    weight: float
    raw: Any = None                # original value, surfaced as evidence


@dataclass
class DomainScore:
    domain: str
    score: float | None            # 0..100, None when no indicators available
    confidence: str
    indicators: dict[str, Any] = field(default_factory=dict)
    note: str | None = None


def linear_decay(distance_m: float, d_min: float, d_max: float) -> float:
    """Full score at/under d_min, zero at/over d_max, linear in between."""
    if distance_m <= d_min:
        return 1.0
    if distance_m >= d_max:
        return 0.0
    return 1.0 - (distance_m - d_min) / (d_max - d_min)


def categorical(value: str, table: dict[str, float], default: float = 0.0) -> float:
    return table.get(value, default)


def score_domain(
    domain: str,
    indicators: list[Indicator],
    confidence: str = "Medium",
    note: str | None = None,
) -> DomainScore:
    """Aggregate indicators, re-normalising weights over those actually present."""
    present = [i for i in indicators if i.value is not None]
    evidence = {i.key: i.raw if i.raw is not None else i.value for i in indicators}

    if not present:
        return DomainScore(domain, None, "Low", evidence, note or "No data available")

    total_w = sum(i.weight for i in present)
    if total_w <= 0:
        return DomainScore(domain, None, "Low", evidence, "Zero total weight")

    agg = sum(i.weight * (i.value or 0.0) for i in present) / total_w
    return DomainScore(domain, round(100 * agg, 1), confidence, evidence, note)


def confidence_from(recency_days: int | None, resolution: str, verified: bool) -> str:
    """Coarse confidence heuristic (refined per domain in Phase 1)."""
    if verified and (recency_days is not None and recency_days <= 180):
        return "High"
    if recency_days is not None and recency_days <= 365:
        return "Medium"
    return "Low"

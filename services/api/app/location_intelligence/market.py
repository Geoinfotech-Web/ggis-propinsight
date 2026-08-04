"""Market domain - geocoded comparable samples with spatial interpolation.

Overview section 4 classifies market prices and trends as Tier 3: geocoded
listing/transaction samples supplied by a partner-agent network, with spatial
aggregation as the delivery layer. No published samples means no score, and
every estimate carries coverage and confidence evidence.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from statistics import median
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.engine import DomainScore, Indicator, score_domain

WEIGHTS: dict[str, float] = {"price_level": 0.5, "trend": 0.3, "yield": 0.2}
SEARCH_RADIUS_M = 10_000.0
MAX_SAMPLES = 250

_PREFERRED_KIND = {
    "home_buyer": "sale",
    "investor": "sale",
    "tenant": "rent",
    "developer": "land",
}


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _group_key(sample: dict[str, Any]) -> tuple[str, str]:
    return str(sample.get("kind") or "unknown"), str(sample.get("unit") or "unspecified")


def _idw_estimate(samples: list[dict[str, Any]]) -> float:
    """Inverse-distance weighted estimate; a 100 m floor prevents singularities."""
    weighted = 0.0
    weights = 0.0
    for sample in samples:
        distance = max(float(sample.get("distance_m") or 0.0), 100.0)
        weight = 1.0 / distance
        weighted += float(sample["value"]) * weight
        weights += weight
    return weighted / weights


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _trend(samples: list[dict[str, Any]], as_of: date) -> tuple[float | None, float | None]:
    recent: list[float] = []
    previous: list[float] = []
    for sample in samples:
        observed = _as_date(sample.get("observed_at"))
        if observed is None:
            continue
        age = (as_of - observed).days
        if 0 <= age <= 365:
            recent.append(float(sample["value"]))
        elif 365 < age <= 730:
            previous.append(float(sample["value"]))
    if len(recent) < 2 or len(previous) < 2:
        return None, None
    old = median(previous)
    if old <= 0:
        return None, None
    growth_pct = 100.0 * (median(recent) - old) / old
    return growth_pct, _clamp((growth_pct + 10.0) / 30.0)


def _yield_proxy(
    samples: list[dict[str, Any]], as_of: date
) -> tuple[float | None, float | None]:
    """Indicative gross yield only when annual rent and sale values are compatible."""
    current = [
        sample
        for sample in samples
        if (observed := _as_date(sample.get("observed_at"))) is not None
        and 0 <= (as_of - observed).days <= 365
    ]
    rents = [
        float(s["value"])
        for s in current
        if s.get("kind") == "rent" and "year" in str(s.get("unit") or "").lower()
    ]
    sales = [
        float(s["value"])
        for s in current
        if s.get("kind") == "sale"
        and str(s.get("unit") or "").upper() in {"NGN", "NGN/PROPERTY"}
    ]
    if not rents or not sales or median(sales) <= 0:
        return None, None
    gross_pct = 100.0 * median(rents) / median(sales)
    return gross_pct, _clamp((gross_pct - 2.0) / 8.0)


def _confidence(samples: list[dict[str, Any]], as_of: date) -> str:
    dated = [_as_date(s.get("observed_at")) for s in samples]
    ages = [(as_of - d).days for d in dated if d is not None]
    recent_days = min(ages) if ages else None
    verified = sum(bool(s.get("verified")) for s in samples)
    if (
        len(samples) >= 15
        and verified >= max(5, len(samples) // 2)
        and recent_days is not None
        and recent_days <= 180
    ):
        return "High"
    if len(samples) >= 5 and recent_days is not None and recent_days <= 365:
        return "Medium"
    return "Low"


def score_market(
    samples: list[dict[str, Any]],
    baselines: dict[tuple[str, str], float],
    *,
    persona: str = "home_buyer",
    as_of: date | None = None,
    radius_m: float = SEARCH_RADIUS_M,
) -> DomainScore:
    """Score persona-relevant market comparables without fabricating missing inputs."""
    as_of = as_of or date.today()
    valid = [s for s in samples if isinstance(s.get("value"), (int, float)) and s["value"] > 0]
    if not valid:
        return DomainScore(
            domain="market",
            score=None,
            confidence="Low",
            indicators={
                "headline": "No published market comparables near this location.",
                "sample_count": 0,
                "coverage_radius_m": radius_m,
                "method": "Geocoded listings and transactions; inverse-distance interpolation.",
            },
            note="Tier 3 market layer has no usable samples for this location.",
        )

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sample in valid:
        groups.setdefault(_group_key(sample), []).append(sample)
    preferred = _PREFERRED_KIND.get(persona, "sale")
    candidate_groups = {k: v for k, v in groups.items() if k[0] == preferred} or groups
    primary_key, primary = max(candidate_groups.items(), key=lambda item: len(item[1]))
    estimate = _idw_estimate(primary)

    baseline = baselines.get(primary_key)
    price_ratio = estimate / baseline if baseline and baseline > 0 else None
    # Affordability/value against the wider published FCT sample.
    price_value = None if price_ratio is None else _clamp((1.4 - price_ratio) / 0.6)
    growth_pct, trend_value = _trend(primary, as_of)
    yield_pct, yield_value = _yield_proxy(valid, as_of)

    ds = score_domain(
        "market",
        [
            Indicator("price_level", price_value, WEIGHTS["price_level"]),
            Indicator("trend", trend_value, WEIGHTS["trend"]),
            Indicator("yield", yield_value, WEIGHTS["yield"]),
        ],
        confidence=_confidence(valid, as_of),
        note=(
            "Tier 3 indicative market read from geocoded partner samples; "
            "spatial estimates are not a formal valuation."
        ),
    )

    kinds = Counter(str(s.get("kind") or "unknown") for s in valid)
    sample_types = Counter(str(s.get("sample_type") or "listing") for s in valid)
    sources = sorted({str(s["source"]) for s in valid if s.get("source")})
    observed = [_as_date(s.get("observed_at")) for s in valid]
    latest = max((d for d in observed if d is not None), default=None)
    ds.indicators = {
        "headline": f"Indicative {primary_key[0]} price from {len(primary)} nearby comparables.",
        "estimated_price": {
            "value": round(estimate, 0),
            "unit": primary_key[1],
            "kind": primary_key[0],
        },
        "price_range": {
            "min": round(min(float(sample["value"]) for sample in primary), 0),
            "max": round(max(float(sample["value"]) for sample in primary), 0),
            "unit": primary_key[1],
            "kind": primary_key[0],
        },
        "trend": (
            "Insufficient two-period sample"
            if growth_pct is None
            else f"{growth_pct:+.1f}% (recent 12 months)"
        ),
        "gross_yield": (
            "Not available from compatible samples"
            if yield_pct is None
            else f"{yield_pct:.1f}% indicative"
        ),
        "sample_count": len(valid),
        "sample_mix": ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items())),
        "record_mix": ", ".join(
            f"{count} {kind}" for kind, count in sorted(sample_types.items())
        ),
        "verified_samples": sum(bool(s.get("verified")) for s in valid),
        "sources": ", ".join(sources) if sources else "Source not supplied",
        "coverage_radius_m": radius_m,
        "as_of": latest.isoformat() if latest else "Observation dates not supplied",
        "method": "Inverse-distance interpolation; wider-layer median benchmark.",
    }
    if persona in {"home_buyer", "tenant"}:
        listing_rows = sorted(
            primary,
            key=lambda sample: (
                _as_date(sample.get("observed_at")) or date.min,
                -float(sample.get("distance_m") or 0.0),
            ),
            reverse=True,
        )
        ds.indicators["listing_kind"] = primary_key[0]
        ds.indicators["listings"] = [
            {
                "id": sample.get("external_id"),
                "title": (
                    sample.get("title")
                    or sample.get("property_type")
                    or "Property listing"
                ),
                "area": sample.get("area"),
                "address": sample.get("address"),
                "bedrooms": sample.get("bedrooms"),
                "property_type": sample.get("property_type"),
                "price": round(float(sample["value"]), 0),
                "unit": primary_key[1],
                "observed_at": (
                    observed_date.isoformat()
                    if (observed_date := _as_date(sample.get("observed_at")))
                    else None
                ),
                "source_url": sample.get("source_url"),
            }
            for sample in listing_rows[:6]
        ]
    return ds


async def market_samples_for_point(
    session: AsyncSession, lon: float, lat: float, radius_m: float = SEARCH_RADIUS_M
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], float]]:
    """Return nearby comparables and wider-layer medians for normalisation."""
    exists = await session.execute(
        text("SELECT to_regclass('public.market_samples') IS NOT NULL AS ok")
    )
    if not bool(exists.scalar()):
        return [], {}

    result = await session.execute(
        text(
            """
            SELECT external_id, title, area, address, bedrooms, property_type,
                   source_url, kind, value, unit, observed_at, source,
                   sample_type, verified,
                   ST_Distance(
                     geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                   ) AS distance_m
            FROM market_samples
            WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                  )
              AND value > 0
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                     observed_at DESC, id
            LIMIT :limit
            """
        ),
        {"lon": lon, "lat": lat, "radius": radius_m, "limit": MAX_SAMPLES},
    )
    samples = [dict(row._mapping) for row in result]

    baseline_result = await session.execute(
        text(
            """
            SELECT kind, COALESCE(unit, 'unspecified') AS unit,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS median_value
            FROM market_samples
            WHERE value > 0
            GROUP BY kind, COALESCE(unit, 'unspecified')
            """
        )
    )
    baselines = {
        (str(row.kind), str(row.unit)): float(row.median_value)
        for row in baseline_result
        if row.median_value is not None
    }
    return samples, baselines

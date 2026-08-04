"""Unit tests for Tier-3 market interpolation and evidence discipline."""
from __future__ import annotations

from datetime import date

from app.location_intelligence.market import score_market


def _sample(
    kind: str,
    value: float,
    observed_at: str,
    *,
    unit: str = "NGN",
    distance_m: float = 1000.0,
    verified: bool = True,
    sample_type: str = "transaction",
    title: str | None = None,
    area: str = "Test Area",
) -> dict:
    return {
        "kind": kind,
        "value": value,
        "unit": unit,
        "observed_at": observed_at,
        "source": "FCT partner agent",
        "sample_type": sample_type,
        "verified": verified,
        "distance_m": distance_m,
        "external_id": f"{kind}-{value}",
        "title": title or f"2 bedroom apartment for {kind}",
        "area": area,
        "address": f"Central {area}",
        "bedrooms": 2,
        "property_type": "Apartment",
        "source_url": "https://example.com/listing",
    }


def test_no_samples_never_fabricates_market_score():
    ds = score_market([], {}, as_of=date(2026, 8, 1))
    assert ds.score is None
    assert ds.confidence == "Low"
    assert ds.indicators["sample_count"] == 0


def test_home_buyer_uses_sale_comparables_and_idw_estimate():
    samples = [
        _sample("sale", 40_000_000, "2026-06-01", distance_m=500),
        _sample("sale", 60_000_000, "2026-05-01", distance_m=1500),
        _sample("land", 12_000_000, "2026-06-01", unit="NGN/plot"),
    ]
    ds = score_market(
        samples,
        {("sale", "NGN"): 60_000_000},
        persona="home_buyer",
        as_of=date(2026, 8, 1),
    )
    estimate = ds.indicators["estimated_price"]
    assert estimate["kind"] == "sale"
    assert estimate["value"] == 45_000_000
    assert ds.indicators["listing_kind"] == "sale"
    assert ds.indicators["price_range"] == {
        "min": 40_000_000,
        "max": 60_000_000,
        "unit": "NGN",
        "kind": "sale",
    }
    assert all(listing["title"] for listing in ds.indicators["listings"])
    assert ds.score is not None


def test_tenant_prefers_rent_samples():
    samples = [
        _sample("sale", 50_000_000, "2026-06-01"),
        _sample("rent", 3_000_000, "2026-06-01", unit="NGN/year"),
        _sample("rent", 3_500_000, "2026-05-01", unit="NGN/year"),
    ]
    ds = score_market(
        samples,
        {("rent", "NGN/year"): 4_000_000},
        persona="tenant",
        as_of=date(2026, 8, 1),
    )
    assert ds.indicators["estimated_price"]["kind"] == "rent"
    assert ds.indicators["listing_kind"] == "rent"
    assert [listing["price"] for listing in ds.indicators["listings"]] == [
        3_000_000,
        3_500_000,
    ]
    assert ds.indicators["price_range"]["unit"] == "NGN/year"


def test_trend_and_yield_require_compatible_samples():
    samples = [
        _sample("sale", 50_000_000, "2026-06-01"),
        _sample("sale", 52_000_000, "2026-02-01"),
        _sample("sale", 40_000_000, "2025-06-01"),
        _sample("sale", 42_000_000, "2025-02-01"),
        _sample("rent", 4_000_000, "2026-06-01", unit="NGN/year"),
    ]
    ds = score_market(
        samples,
        {("sale", "NGN"): 55_000_000},
        persona="investor",
        as_of=date(2026, 8, 1),
    )
    assert "% (recent 12 months)" in ds.indicators["trend"]
    assert ds.indicators["gross_yield"] == "7.8% indicative"
    assert "listings" not in ds.indicators
    assert "listing_kind" not in ds.indicators


def test_developer_does_not_receive_property_listings():
    samples = [
        _sample("land", 25_000_000, "2026-06-01", unit="NGN/plot"),
        _sample("sale", 50_000_000, "2026-06-01"),
    ]
    ds = score_market(
        samples,
        {("land", "NGN/plot"): 30_000_000},
        persona="developer",
        as_of=date(2026, 8, 1),
    )
    assert "listings" not in ds.indicators
    assert "listing_kind" not in ds.indicators


def test_confidence_reflects_depth_recency_and_verification():
    samples = [
        _sample("sale", 50_000_000 + i * 100_000, "2026-07-01", distance_m=500 + i)
        for i in range(15)
    ]
    ds = score_market(
        samples,
        {("sale", "NGN"): 55_000_000},
        as_of=date(2026, 8, 1),
    )
    assert ds.confidence == "High"
    assert ds.indicators["verified_samples"] == 15

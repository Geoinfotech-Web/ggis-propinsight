"""Tests for the overall scorecard insight and quality bands."""
from __future__ import annotations

from app.location_intelligence.summary import build_highlights, build_summary, quality_band


class _D:
    def __init__(
        self,
        score,
        *,
        score_direction="higher_is_better",
        included_in_fit=True,
        rating=None,
    ):
        self.score = score
        self.score_direction = score_direction
        self.included_in_fit = included_in_fit
        self.rating = rating


def test_quality_bands():
    assert quality_band(85) == "Strong"
    assert quality_band(55) == "Moderate"
    assert quality_band(20) == "Weak"
    assert quality_band(None) is None


def test_consumer_summary_gives_verdict_and_introduces_reasons():
    domains = {"amenities": _D(92), "security": _D(48), "flood": _D(80)}
    text = build_summary("home_buyer", "Home Buyer", 88.0, domains)
    assert "strong choice for buying a home" in text.lower()
    assert "what supports the result" in text.lower()


def test_summary_no_concern_when_all_strong():
    domains = {"amenities": _D(90), "flood": _D(85)}
    text = build_summary("investor", "Investor", 88.0, domains)
    assert "for an Investor" in text
    assert "watch" not in text.lower()


def test_summary_handles_no_scores():
    text = build_summary("tenant", "Tenant", None, {"market": _D(None)})
    assert "not enough information" in text.lower()


def test_tenant_summary_uses_renter_language():
    domains = {"accessibility": _D(88), "market": _D(35)}
    text = build_summary("tenant", "Tenant", 61.0, domains)
    assert "good option for renting" in text.lower()
    assert "what you should check" in text.lower()


def test_highlights_include_strength_concern_and_priority():
    domains = {
        "flood": _D(85),
        "security": _D(25),
        "amenities": _D(60),
    }
    highlights = build_highlights(
        "home_buyer",
        domains,
        ["flood", "amenities", "security"],
    )
    assert len(highlights) == 3
    assert highlights[0]["domain"] == "flood"
    assert highlights[0]["tone"] == "positive"
    assert highlights[1]["domain"] == "security"
    assert highlights[1]["tone"] == "caution"


def test_tenant_market_highlight_mentions_full_rental_cost():
    highlights = build_highlights(
        "tenant",
        {"amenities": _D(80), "market": _D(20)},
        ["amenities", "market"],
    )
    market = next(item for item in highlights if item["domain"] == "market")
    assert "rent and service charges" in market["text"].lower()


def test_high_flood_hazard_is_a_caution_with_exact_risk_class():
    highlights = build_highlights(
        "home_buyer",
        {
            "flood": _D(
                80,
                score_direction="higher_is_worse",
                rating="High flood risk",
            ),
            "amenities": _D(70),
        },
        ["flood", "amenities"],
    )
    flood = next(item for item in highlights if item["domain"] == "flood")
    assert flood["tone"] == "caution"
    assert flood["title"] == "Flood risk"
    assert "high flood risk" in flood["text"].lower()


def test_demo_flood_is_not_used_as_a_highlight():
    highlights = build_highlights(
        "tenant",
        {
            "flood": _D(10, included_in_fit=False, rating="Very Low flood risk"),
            "amenities": _D(70),
        },
        ["flood", "amenities"],
    )
    assert all(item["domain"] != "flood" for item in highlights)

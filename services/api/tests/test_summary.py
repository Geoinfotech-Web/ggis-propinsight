"""Tests for the overall scorecard insight and quality bands."""
from __future__ import annotations

from app.location_intelligence.summary import build_summary, quality_band


class _D:
    def __init__(self, score):
        self.score = score


def test_quality_bands():
    assert quality_band(85) == "Strong"
    assert quality_band(55) == "Moderate"
    assert quality_band(20) == "Weak"
    assert quality_band(None) is None


def test_summary_names_strength_and_concern():
    domains = {"amenities": _D(92), "security": _D(48), "flood": _D(80)}
    text = build_summary("Home Buyer", 88.0, domains)
    assert "strong match" in text.lower()
    assert "Home Buyer" in text
    assert "nearby amenities" in text     # strongest
    assert "safety" in text               # weakest (security < 70)


def test_summary_no_concern_when_all_strong():
    domains = {"amenities": _D(90), "flood": _D(85)}
    text = build_summary("Investor", 88.0, domains)
    assert "watch" not in text.lower()


def test_summary_handles_no_scores():
    text = build_summary("Tenant", None, {"market": _D(None)})
    assert "data" in text.lower()

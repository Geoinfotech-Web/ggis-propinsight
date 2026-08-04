"""Unit tests for amenities scoring (fct-v1 + linear decay)."""
from __future__ import annotations

from app.location_intelligence.amenities import (
    AMENITY_WEIGHTS,
    NEARBY_CATEGORIES,
    score_amenities,
)
from app.scoring.engine import linear_decay


def test_amenities_score_full_when_all_nearby():
    distances = {cat: 100.0 for cat in AMENITY_WEIGHTS}
    ds = score_amenities(distances)
    assert ds.score == 100.0
    assert ds.confidence == "Medium"


def test_amenities_score_none_when_all_missing():
    distances = {cat: None for cat in AMENITY_WEIGHTS}
    ds = score_amenities(distances)
    assert ds.score is None
    assert ds.confidence == "Low"


def test_amenities_renormalises_over_present_indicators():
    distances = {cat: None for cat in AMENITY_WEIGHTS}
    distances["school"] = 100.0  # full credit
    distances["hospital"] = 5000.0  # zero credit at d_max
    ds = score_amenities(distances)
    # Only school (0.20) and hospital (0.20) present → equal weights → 50
    assert ds.score == 50.0
    assert "school" in ds.indicators
    assert ds.indicators["school"]["distance_m"] == 100.0


def test_amenities_includes_name_in_evidence_raw():
    nearest = {cat: None for cat in AMENITY_WEIGHTS}
    nearest["school"] = {"distance_m": 420.4, "name": "Demo Primary School"}
    nearest["hospital"] = {"distance_m": 800.0, "name": None}
    ds = score_amenities(nearest)
    assert ds.indicators["school"]["name"] == "Demo Primary School"
    assert ds.indicators["school"]["distance_m"] == 420.4
    assert "name" not in ds.indicators["hospital"]
    assert ds.indicators["hospital"]["distance_m"] == 800.0


def test_linear_decay_midpoint():
    assert linear_decay(2750, 500, 5000) == 0.5


def test_map_amenity_categories_cover_requested_layers():
    assert set(NEARBY_CATEGORIES) == {
        "school",
        "hospital",
        "market",
        "bank",
        "power",
        "fuel",
    }

"""Unit tests for accessibility scoring / landmarks."""
from __future__ import annotations

from app.location_intelligence.accessibility import haversine_m, score_accessibility


def test_haversine_zero_at_same_point():
    assert haversine_m(7.5, 9.0, 7.5, 9.0) == 0.0


def test_accessibility_with_road_and_landmarks():
    ds = score_accessibility(50.0, lon=7.4913, lat=9.0579)
    assert ds.score is not None
    assert "road_distance" in ds.indicators
    assert "cbd_time" in ds.indicators
    assert ds.indicators["road_distance"]["distance_m"] == 50.0


def test_accessibility_landmarks_without_road():
    ds = score_accessibility(None, lon=7.4913, lat=9.0579)
    assert ds.score is not None
    assert ds.indicators["road_distance"] is None or "distance_m" not in (
        ds.indicators.get("road_distance") or {}
    )

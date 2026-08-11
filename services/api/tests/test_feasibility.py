"""Unit tests for feasibility scoring."""
from __future__ import annotations

from app.location_intelligence.feasibility import available_weight, score_feasibility


def test_feasibility_high_when_flat_dry_and_safe():
    ds = score_feasibility(
        slope_deg=2.0,
        flood_normalised=1.0,
        utility_distance_m=100.0,
        twi=4.0,
    )
    assert ds.score == 100.0


def test_feasibility_renormalises_when_some_missing():
    ds = score_feasibility(
        slope_deg=2.0,
        flood_normalised=None,
        utility_distance_m=None,
        twi=None,
    )
    assert ds.score == 100.0
    assert "slope" in ds.indicators


def test_steep_slope_lowers_score():
    good = score_feasibility(
        slope_deg=2.0, flood_normalised=1.0, utility_distance_m=100.0, twi=4.0
    )
    steep = score_feasibility(
        slope_deg=25.0, flood_normalised=1.0, utility_distance_m=100.0, twi=4.0
    )
    assert steep.score is not None and good.score is not None
    assert steep.score < good.score


def test_buildable_share_replaces_single_point_slope_for_terrain_component():
    result = score_feasibility(
        buildable_share_pct=50.0,
        flood_normalised=1.0,
        utility_distance_m=100.0,
        twi=4.0,
    )
    assert result.indicators["slope"]["buildable_share_pct"] == 50.0
    assert result.score == 85.0


def test_feasibility_availability_threshold_inputs_are_auditable():
    assert available_weight(terrain=True, flood=False, utility=False, wetness=True) == 0.5
    assert available_weight(terrain=True, flood=True, utility=False, wetness=True) == 0.75

"""Tests for the layer_version discipline pure logic (no DB required)."""
from __future__ import annotations

from datetime import datetime

from aia_etl.layers import is_stale, next_calver


def test_next_calver_starts_at_one():
    assert next_calver(None, datetime(2026, 7, 1)) == "2026.07.1"


def test_next_calver_increments_within_month():
    assert next_calver("2026.07.1", datetime(2026, 7, 15)) == "2026.07.2"
    assert next_calver("2026.07.9", datetime(2026, 7, 20)) == "2026.07.10"


def test_next_calver_resets_on_new_month():
    assert next_calver("2026.06.3", datetime(2026, 7, 1)) == "2026.07.1"


def test_next_calver_tolerates_garbage_previous():
    assert next_calver("nonsense", datetime(2026, 7, 1)) == "2026.07.1"


def test_is_stale_only_flags_referenced_layer():
    lv = {"poi": "2026.06.1", "roads": "2026.06.1"}
    # poi bumped -> stale
    assert is_stale(lv, "poi", "2026.07.1") is True
    # roads unchanged -> fresh
    assert is_stale(lv, "roads", "2026.06.1") is False
    # a layer the score never used -> not made stale
    assert is_stale(lv, "hazard", "ggis-fw-2.4") is False

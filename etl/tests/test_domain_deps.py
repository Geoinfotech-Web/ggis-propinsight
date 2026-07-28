"""Tests for the Phase 1 domain → layer readiness map."""
from __future__ import annotations

from aia_etl.domain_deps import (
    DOMAIN_DEPENDENCIES,
    PHASE1_PIPELINE_PRIORITY,
    layers_ready,
    pending_note,
    readiness_snapshot,
)


def test_phase1_priority_starts_with_osm():
    assert PHASE1_PIPELINE_PRIORITY[0].endswith("refresh_osm")


def test_amenities_blocked_without_poi():
    assert layers_ready(("poi",), {}) is False
    assert layers_ready(("poi",), {"poi": "unpublished"}) is False
    assert layers_ready(("poi",), {"poi": "2026.07.1"}) is True


def test_accessibility_needs_roads_and_poi():
    assert layers_ready(("roads", "poi"), {"roads": "2026.07.1"}) is False
    assert layers_ready(("roads", "poi"), {"roads": "2026.07.1", "poi": "2026.07.1"}) is True


def test_pending_note_names_missing_layers():
    note = pending_note("amenities", {"poi": "unpublished"})
    assert "poi" in note
    assert "Phase 1" in note


def test_later_tier_note():
    note = pending_note("market", {})
    assert "later phase" in note.lower()


def test_readiness_snapshot_marks_flood_ready():
    rows = readiness_snapshot({})
    by_domain = {r["domain"]: r for r in rows}
    assert by_domain["flood"]["ready"] is True
    assert by_domain["amenities"]["ready"] is False
    assert len(DOMAIN_DEPENDENCIES) == 8

"""Tests for domain readiness gates."""
from __future__ import annotations

from app.location_intelligence.readiness import layers_ready, pending_note, readiness_rows


def test_amenities_pending_names_poi():
    note = pending_note("amenities", {})
    assert "poi" in note


def test_amenities_ready_when_poi_published():
    rows = readiness_rows({"poi": "2026.07.1", "roads": "2026.07.1", "dem": "2026.07.1"})
    by_domain = {r["domain"]: r for r in rows}
    assert by_domain["amenities"]["ready"] is True
    assert by_domain["accessibility"]["ready"] is True
    assert by_domain["feasibility"]["ready"] is True
    assert by_domain["flood"]["ready"] is True


def test_feasibility_not_ready_without_dem():
    rows = readiness_rows({"poi": "2026.07.1"})
    by_domain = {r["domain"]: r for r in rows}
    assert by_domain["feasibility"]["ready"] is False
    assert by_domain["amenities"]["ready"] is True


def test_layers_ready():
    assert layers_ready({"poi": "2026.07.1"}, ("poi",)) is True
    assert layers_ready({}, ("poi",)) is False


def test_market_requires_published_partner_sample_layer():
    pending = {r["domain"]: r for r in readiness_rows({})}["market"]
    ready = {
        r["domain"]: r for r in readiness_rows({"market": "2026.08.1"})
    }["market"]
    assert pending["ready"] is False
    assert pending["required_layers"] == ["market"]
    assert ready["ready"] is True

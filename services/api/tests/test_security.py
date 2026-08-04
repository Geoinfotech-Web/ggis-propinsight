"""Unit tests for district-level security scoring."""
from __future__ import annotations

from app.location_intelligence.security import score_security


def test_more_incidents_lowers_score():
    calm = score_security(incident_total=2, police_distance_m=500.0, district="Maitama")
    busy = score_security(incident_total=25, police_distance_m=500.0, district="Wuse")
    assert calm.score is not None and busy.score is not None
    assert calm.score > busy.score


def test_closer_police_raises_score():
    near = score_security(incident_total=10, police_distance_m=300.0)
    far = score_security(incident_total=10, police_distance_m=5500.0)
    assert near.score is not None and far.score is not None
    assert near.score > far.score


def test_district_name_in_note_and_aggregate_framing():
    ds = score_security(incident_total=5, police_distance_m=700.0, district="Central Area")
    assert "Central Area" in (ds.note or "")
    assert "district-level" in (ds.note or "").lower()


def test_missing_inputs_do_not_crash():
    ds = score_security(incident_total=None, police_distance_m=None)
    # No indicators present -> no score, low confidence (never fabricated).
    assert ds.score is None
    assert ds.confidence == "Low"

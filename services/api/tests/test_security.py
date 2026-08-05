"""Unit tests for privacy-preserving local security scoring."""
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
    # Aggregate framing: never implies street-level crime data.
    assert "street-level" in (ds.note or "").lower()


def test_evidence_is_public_readable():
    ds = score_security(
        incident_total=11,
        police_distance_m=419.3,
        period="2026-Q2",
        by_category={"theft": 8, "burglary": 3},
        district="Central Area",
        incident_source="demo-seed",
    )
    ev = ds.indicators
    assert ev["safety_level"] == "Generally safe"
    assert ev["reported_incidents"] == "11 reports (Apr–Jun 2026)"
    assert ev["most_common"] == "8 theft, 3 burglary"
    assert ev["nearest_police"] == {"distance_m": 419.3}
    assert ev["coverage"] == "District-level incident reports (Central Area)"
    assert ev["data_source"] == "Pilot demonstration data"


def test_ward_context_labels_district_fallback_honestly():
    ds = score_security(
        incident_total=7,
        police_distance_m=900.0,
        district="Abuja Municipal",
        ward="Garki",
        aggregation_level="district",
    )
    assert "Garki ward" in ds.indicators["coverage"]
    assert "aggregated for Abuja Municipal" in ds.indicators["coverage"]
    assert "broader Abuja Municipal aggregate" in (ds.note or "")


def test_true_ward_aggregate_is_labelled_ward_level():
    ds = score_security(
        incident_total=3,
        police_distance_m=600.0,
        district="Abuja Municipal",
        ward="Garki",
        aggregation_level="ward",
    )
    assert ds.indicators["coverage"] == "Ward-level incident reports (Garki)"


def test_missing_inputs_do_not_crash():
    ds = score_security(incident_total=None, police_distance_m=None)
    # No indicators present -> no score, low confidence (never fabricated).
    assert ds.score is None
    assert ds.confidence == "Low"

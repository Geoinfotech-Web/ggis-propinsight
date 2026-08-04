"""Unit tests for advisory tenure scoring from planning overlays."""
from __future__ import annotations

from app.location_intelligence.tenure import score_tenure


def _ov(kind: str) -> dict:
    return {"kind": kind, "status": "x", "source_doc": "doc", "effective_date": None}


def test_acquisition_is_high_risk():
    ds = score_tenure([_ov("acquisition")])
    assert ds.score is not None and ds.score <= 20
    assert "acquisition" in (ds.note or "").lower()


def test_approved_layout_raises_confidence_score():
    baseline = score_tenure([])
    layout = score_tenure([_ov("layout")])
    assert layout.score is not None and baseline.score is not None
    assert layout.score > baseline.score


def test_restrictions_reduce_score():
    layout = score_tenure([_ov("layout")])
    restricted = score_tenure([_ov("layout"), _ov("setback"), _ov("corridor")])
    assert restricted.score is not None and layout.score is not None
    assert restricted.score < layout.score


def test_always_flagged_advisory_low_confidence():
    ds = score_tenure([_ov("layout")])
    assert ds.confidence == "Low"
    assert ds.indicators.get("advisory") is True
    assert "advisory" in (ds.note or "").lower()

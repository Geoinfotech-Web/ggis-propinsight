"""Tests for the ETL QA-rule framework."""
from __future__ import annotations

from aia_etl.qa import (
    FCT_BBOX,
    require_geometry,
    run_rules,
    valid_category,
    within_bbox,
)


def _rec(**kw):
    base = {"category": "school", "lon": 7.49, "lat": 9.06}
    base.update(kw)
    return base


def test_passes_valid_record():
    report = run_rules([_rec()], [require_geometry, valid_category, within_bbox(FCT_BBOX)])
    assert report.summary()["passed"] == 1
    assert report.reject_rate == 0.0


def test_rejects_missing_geometry():
    report = run_rules([{"category": "school"}], [require_geometry])
    assert len(report.rejected) == 1
    assert report.rejected[0][1] == "missing geometry"


def test_rejects_invalid_category():
    report = run_rules([_rec(category="nightclub")], [valid_category])
    assert report.rejected[0][1].startswith("invalid category")


def test_rejects_point_outside_aoi():
    # Lagos-ish coordinate, well outside the FCT bbox.
    report = run_rules([_rec(lon=3.39, lat=6.45)], [within_bbox(FCT_BBOX)])
    assert report.rejected[0][1] == "outside AOI bbox"


def test_reject_rate_mixed_batch():
    records = [_rec(), _rec(category="bad"), _rec(lon=3.39, lat=6.45)]
    report = run_rules(records, [require_geometry, valid_category, within_bbox(FCT_BBOX)])
    assert report.total == 3
    assert len(report.passed) == 1
    assert round(report.reject_rate, 2) == 0.67

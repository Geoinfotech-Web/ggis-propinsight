"""Tests for open land-use taxonomy and Overture query construction."""
from __future__ import annotations

from aia_etl.sources.base import FCT_BBOX
from aia_etl.sources.overture_land_use import build_sql, geometry_bounds, normalise_category


def test_land_use_categories_cover_investor_and_developer_decisions():
    assert normalise_category("residential", "residential") == "residential"
    assert normalise_category("industrial", "developed") == "industrial"
    assert normalise_category("commercial", "developed") == "commercial"
    assert normalise_category("school", "education") == "institutional"
    assert normalise_category("nature_reserve", "protected") == "protected_reserve"
    assert normalise_category("military", "military") == "military_restricted"
    assert normalise_category("farmland", "agriculture") == "agricultural"


def test_land_use_sql_uses_polygonal_current_release_data():
    sql = build_sql(FCT_BBOX, "2026-07-22.0")
    assert "theme=base/type=land_use" in sql
    assert "release/2026-07-22.0/" in sql
    assert "ST_AsGeoJSON(geometry)" in sql
    assert "'POLYGON', 'MULTIPOLYGON'" in sql


def test_geometry_bounds_exposes_antimeridian_scale_geometry():
    geometry = (
        '{"type":"Polygon","coordinates":[[[-177,-3],[170,-3],'
        '[170,22],[-177,22],[-177,-3]]]} '
    )
    assert geometry_bounds(geometry) == (-177.0, -3.0, 170.0, 22.0)

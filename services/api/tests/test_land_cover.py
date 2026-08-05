from app.location_intelligence.land_cover import _class_info, _tile_bounds


def test_class_info_is_explicitly_observed_not_zoning():
    raster = {
        "classes": {"50": {"key": "built_up", "label": "Built-up", "color": "#fa0000"}},
        "source": "ESA WorldCover 2021 v200",
        "source_url": "https://example.test/worldcover",
        "period_start": None,
        "period_end": None,
        "resolution_m": 10,
    }
    result = _class_info(raster, 50)
    assert result is not None
    assert result["category"] == "built_up"
    assert result["designation"] == "observed_land_cover"
    assert "not statutory zoning" in result["advisory"]


def test_web_mercator_tile_bounds_cover_world_at_zoom_zero():
    left, bottom, right, top = _tile_bounds(0, 0, 0)
    assert round(left) == -20037508
    assert round(bottom) == -20037508
    assert round(right) == 20037508
    assert round(top) == 20037508

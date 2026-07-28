"""Tests for OSM tag -> AIA category mapping."""
from __future__ import annotations

from aia_etl.poi_categories import AIA_CATEGORIES, categorize, osm_selectors_for


def test_maps_core_amenities():
    assert categorize({"amenity": "school"}) == "school"
    assert categorize({"amenity": "hospital"}) == "hospital"
    assert categorize({"amenity": "fuel"}) == "fuel"
    assert categorize({"amenity": "bank"}) == "bank"
    assert categorize({"amenity": "place_of_worship"}) == "worship"


def test_maps_shops_and_infrastructure():
    assert categorize({"shop": "supermarket"}) == "market"
    assert categorize({"power": "substation"}) == "power"
    assert categorize({"man_made": "borehole"}) == "water"


def test_isp_mast_fallback():
    assert categorize({"man_made": "mast", "tower:type": "communication"}) == "isp"


def test_irrelevant_tags_return_none():
    assert categorize({"amenity": "bench"}) is None
    assert categorize({"highway": "residential"}) is None
    assert categorize({}) is None


def test_every_category_has_at_least_one_selector_or_is_fallback():
    for cat in AIA_CATEGORIES:
        if cat == "isp":
            continue  # isp is matched via the mast fallback, not the tag map
        assert osm_selectors_for(cat), f"no OSM selectors for {cat}"

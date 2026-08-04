"""Tests for multi-source POI ingestion (pure logic; no network/DB)."""
from __future__ import annotations

from aia_etl.sources.arcgis import build_params, map_feature
from aia_etl.sources.base import FCT_BBOX, PoiRecord, dedup_records
from aia_etl.sources.overpass import build_query, map_element
from aia_etl.sources.overture import map_overture_category


def test_poi_record_validity_and_bbox():
    inside = PoiRecord(7.49, 9.06, "school", "X", "overpass")
    outside = PoiRecord(3.39, 6.45, "school", "Y", "overpass")  # Lagos
    bad_cat = PoiRecord(7.49, 9.06, "nightclub", "Z", "overpass")
    assert inside.valid(FCT_BBOX) is True
    assert outside.valid(FCT_BBOX) is False
    assert bad_cat.valid(FCT_BBOX) is False


def test_dedup_prefers_named_and_collapses_duplicates():
    recs = [
        PoiRecord(7.49000, 9.06000, "bank", None, "overpass"),
        PoiRecord(7.49001, 9.06001, "bank", "Zenith Bank", "overture"),  # same cell
        PoiRecord(7.50000, 9.07000, "bank", "GTBank", "overpass"),       # different
    ]
    out = dedup_records(recs)
    assert len(out) == 2
    named = [r for r in out if r.name == "Zenith Bank"]
    assert named, "named record should win over the unnamed duplicate"


def test_overpass_maps_node_and_way():
    node = {"type": "node", "lon": 7.49, "lat": 9.06, "tags": {"amenity": "school", "name": "GSS"}}
    way = {"type": "way", "center": {"lon": 7.5, "lat": 9.07},
           "tags": {"amenity": "hospital", "name": "Nat'l"}}
    irrelevant = {"type": "node", "lon": 7.49, "lat": 9.06, "tags": {"amenity": "bench"}}
    r1, r2 = map_element(node), map_element(way)
    assert r1 and r1.category == "school" and r1.source == "overpass"
    assert r2 and r2.category == "hospital" and r2.lon == 7.5
    assert map_element(irrelevant) is None


def test_overpass_query_covers_bbox():
    q = build_query((6.75, 8.25, 7.75, 9.35))
    assert "8.25,6.75,9.35,7.75" in q  # S,W,N,E
    assert 'node["amenity"="school"]' in q


def test_overture_category_mapping():
    assert map_overture_category("primary_and_secondary_school") == "school"
    assert map_overture_category("hospital") == "hospital"
    assert map_overture_category("bank_credit_union") == "bank"
    assert map_overture_category("gas_station") == "fuel"
    assert map_overture_category("night_club") is None
    assert map_overture_category(None) is None


def test_arcgis_feature_mapping_and_name_fallback():
    feat = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [7.49, 9.06]},
        "properties": {"prmry_name": "Wuse District Hospital"},
    }
    rec = map_feature(feat, "hospital")  # no explicit name_field -> fallback
    assert rec and rec.category == "hospital" and rec.source == "grid3"
    assert rec.name == "Wuse District Hospital"
    assert rec.lon == 7.49 and rec.lat == 9.06

    non_point = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []},
                 "properties": {}}
    assert map_feature(non_point, "hospital") is None


def test_arcgis_query_params_carry_bbox():
    p = build_params((6.75, 8.25, 7.75, 9.35), offset=0)
    assert p["geometry"] == "6.75,8.25,7.75,9.35"
    assert p["f"] == "geojson" and p["inSR"] == "4326"

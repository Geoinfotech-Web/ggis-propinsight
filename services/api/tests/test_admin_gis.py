from __future__ import annotations

from app.admin_gis import _validate_collection


def _collection(props: dict, geometry_type: str = "Polygon") -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": props.get("source_id", "one"),
                "geometry": {
                    "type": geometry_type,
                    "coordinates": [[
                        [7.0, 9.0],
                        [7.1, 9.0],
                        [7.1, 9.1],
                        [7.0, 9.1],
                        [7.0, 9.0],
                    ]],
                },
                "properties": props,
            }
        ],
    }


def test_admin_gis_validation_accepts_valid_geojson_batch():
    report = _validate_collection(
        "lgas",
        _collection({"source_id": "lga-1", "name": "Gwagwalada", "state_code": "FC"}),
        {},
        None,
    )

    assert report["publishable"] is True
    assert report["feature_count"] == 1
    assert report["errors"] == []


def test_admin_gis_validation_blocks_wrong_geometry_and_missing_attributes():
    report = _validate_collection(
        "masterplans",
        _collection({"source_id": "mp-1"}, geometry_type="Point"),
        {},
        None,
    )

    assert report["publishable"] is False
    assert any("expected polygon" in error for error in report["errors"])
    assert any("category" in error for error in report["errors"])
    assert any("state_code" in error for error in report["errors"])


def test_admin_gis_validation_uses_attribute_mapping():
    report = _validate_collection(
        "wards",
        _collection({"WARD_ID": "w-1", "WARD_NAME": "Kutunku", "LGA": "Gwagwalada"}),
        {"source_id": "WARD_ID", "name": "WARD_NAME", "area_council": "LGA"},
        "FC",
    )

    assert report["publishable"] is True

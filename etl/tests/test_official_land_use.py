from aia_etl.sources.official_land_use import (
    normalise_official_category,
    records_from_feature_collection,
)


def test_official_categories_cover_planning_terms():
    assert normalise_official_category("Low Density Residential") == "residential"
    assert normalise_official_category("Industrial II") == "industrial"
    assert normalise_official_category("Green Belt Reserve") == "protected_reserve"
    assert normalise_official_category("Recreational Open Space") == "recreation_open_space"


def test_official_records_require_polygons_and_category_field():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "id": 9,
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[7.4, 9.0], [7.5, 9.0], [7.5, 9.1], [7.4, 9.0]]],
                },
                "properties": {"ZONE": "Commercial", "NAME": "District centre"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [7.45, 9.05]},
                "properties": {"ZONE": "Residential"},
            },
        ],
    }
    records = records_from_feature_collection(
        payload,
        dataset_name="FCT Plan",
        category_field="ZONE",
        name_field="NAME",
    )
    assert len(records) == 1
    assert records[0].category == "commercial"
    assert records[0].name == "District centre"
    assert records[0].source_id.startswith("official:")

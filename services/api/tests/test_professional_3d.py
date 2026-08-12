"""Tests for bounded professional 3D evidence responses."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.location_intelligence.professional_3d import (
    BUILDING_ADVISORY,
    building_feature_collection,
    validate_context_bbox,
    vegetation_feature_collection,
)


class _Result:
    def __init__(self, *, scalar=None, rows=None):  # noqa: ANN001
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):  # noqa: ANN201
        return self._scalar

    def scalar_one(self):  # noqa: ANN201
        return self._scalar

    def all(self):  # noqa: ANN201
        return self._rows


class _Session:
    def __init__(self, results):  # noqa: ANN001
        self.results = iter(results)

    async def execute(self, statement, params=None):  # noqa: ANN001, ANN201
        return next(self.results)


def test_professional_bbox_is_limited_to_nearest_three_kilometres():
    validate_context_bbox((7.453, 9.043, 7.507, 9.097), (7.48, 9.07))
    with pytest.raises(HTTPException, match="nearest 3 km"):
        validate_context_bbox((7.40, 9.00, 7.56, 9.14), (7.48, 9.07))


@pytest.mark.asyncio
async def test_unpublished_buildings_return_advisory_without_querying_features():
    session = _Session([_Result(scalar="unpublished")])
    result = await building_feature_collection(
        session, (7.453, 9.043, 7.507, 9.097), (7.48, 9.07)
    )
    assert result["features"] == []
    assert result["metadata"]["advisory"] == BUILDING_ADVISORY


@pytest.mark.asyncio
async def test_building_response_exposes_height_basis_and_truncation():
    row = SimpleNamespace(
        source_id="building-1",
        parent_source_id=None,
        feature_type="building",
        building_class="house",
        height_m=None,
        num_floors=None,
        min_height_m=None,
        display_height_m=6.0,
        height_basis="default_visual",
        source_datasets=["Microsoft ML Buildings"],
        release="2026-07-22.0",
        geometry='{"type":"Polygon","coordinates":[[[7,9],[7.1,9],[7.1,9.1],[7,9]]]}',
    )
    session = _Session(
        [_Result(scalar="2026.08.1"), _Result(scalar=2), _Result(rows=[row])]
    )
    result = await building_feature_collection(
        session, (7.453, 9.043, 7.507, 9.097), (7.48, 9.07), limit=1
    )
    assert result["metadata"]["truncated"] is True
    assert result["metadata"]["release"] == "2026-07-22.0"
    assert result["features"][0]["properties"]["height_basis"] == "default_visual"


@pytest.mark.asyncio
async def test_vegetation_response_exposes_observation_provenance():
    row = SimpleNamespace(
        id=7,
        source="ESA WorldCover 2021 v200",
        source_url="https://esa-worldcover.org/",
        period_start=None,
        period_end=None,
        resolution_m=10,
        area_ha=3.4,
        geometry='{"type":"Polygon","coordinates":[[[7,9],[7.1,9],[7.1,9.1],[7,9]]]}',
    )
    session = _Session(
        [_Result(scalar="2026.08.1"), _Result(scalar=1), _Result(rows=[row])]
    )
    result = await vegetation_feature_collection(
        session, (7.453, 9.043, 7.507, 9.097), (7.48, 9.07)
    )
    assert result["metadata"]["source"] == "ESA WorldCover 2021 v200"
    assert result["metadata"]["resolution_m"] == 10
    assert result["features"][0]["properties"]["height_basis"] == "illustrative_canopy"

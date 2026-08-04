"""Tests for land-use map and point evidence."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.location_intelligence.land_use import ADVISORY, land_use_at_point


class _Result:
    def __init__(self, *, scalar=None, row=None):  # noqa: ANN001
        self._scalar = scalar
        self._row = row

    def scalar(self):  # noqa: ANN201
        return self._scalar

    def first(self):  # noqa: ANN201
        return self._row


class _Session:
    def __init__(self, results):  # noqa: ANN001
        self.results = iter(results)

    async def execute(self, statement, params=None):  # noqa: ANN001, ANN201
        return next(self.results)


@pytest.mark.asyncio
async def test_land_use_point_is_labeled_and_explicitly_advisory():
    row = SimpleNamespace(
        category="industrial",
        name="Idu Industrial Area",
        source_class="industrial",
        source_subtype="developed",
        designation="observed_reference",
        source="Overture Maps / OpenStreetMap",
        source_url="https://example.test/source",
        effective_date=None,
    )
    session = _Session([_Result(scalar="2026.08.1"), _Result(row=row)])

    result = await land_use_at_point(session, 7.36, 9.05)

    assert result is not None
    assert result["label"] == "Industrial"
    assert result["designation"] == "observed_reference"
    assert result["advisory"] == ADVISORY
    assert "AGIS/FCTA" in result["advisory"]


@pytest.mark.asyncio
async def test_unpublished_land_use_returns_no_point_classification():
    session = _Session([_Result(scalar="unpublished")])

    assert await land_use_at_point(session, 7.36, 9.05) is None

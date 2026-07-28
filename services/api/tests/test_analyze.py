"""Unit tests for the scorecard fan-out and GGIS graceful degradation (TDD §5.3)."""
from __future__ import annotations

import pytest

from app.flood.client import FloodResult, FloodStatus
from app.location_intelligence.schemas import AnalyzeRequest, GeoJSONGeometry
from app.location_intelligence.service import analyze


class _StubFlood:
    """Stubs the GGIS client so tests don't hit the network."""

    def __init__(self, result: FloodResult) -> None:
        self._result = result
        self.calls = 0

    async def risk(self, geometry, last_known=None):  # noqa: ANN001
        self.calls += 1
        return self._result


class _FakeCache:
    """In-memory stand-in for ScorecardCache with the same interface."""

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    @staticmethod
    def make_key(profile, geohash8, layer_versions):  # noqa: ANN001
        import json

        return f"{profile}:{geohash8}:{json.dumps(layer_versions, sort_keys=True)}"

    async def get(self, key):  # noqa: ANN001
        return self.store.get(key)

    async def set(self, key, value):  # noqa: ANN001
        self.store[key] = value


def _req() -> AnalyzeRequest:
    return AnalyzeRequest(geometry=GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634]))


@pytest.mark.asyncio
async def test_analyze_returns_all_eight_domains():
    ok = FloodResult(
        status=FloodStatus.OK, risk_class="High", risk_score=0.78, normalised=0.2,
        factors={"elevation_m": 342.1}, model_version="ggis-fw-2.3",
        data_currency="2026-06-30", confidence="high",
    )
    res = await analyze(_req(), flood=_StubFlood(ok))  # type: ignore[arg-type]
    assert set(res.domains) == {
        "flood", "security", "amenities", "accessibility",
        "tenure", "market", "livability", "feasibility",
    }
    assert res.domains["flood"].score == 20.0  # 100 * 0.2
    assert res.domains["flood"].status == "ok"
    assert res.layer_versions["hazard"] == "ggis-fw-2.3"


@pytest.mark.asyncio
async def test_flood_degrades_gracefully_when_ggis_unavailable():
    degraded = FloodResult(
        status=FloodStatus.DEGRADED, risk_class=None, risk_score=None, normalised=None,
        factors={}, model_version=None, data_currency=None, confidence=None,
        stale=True, message="Flood domain temporarily unavailable.",
    )
    res = await analyze(_req(), flood=_StubFlood(degraded))  # type: ignore[arg-type]
    flood = res.domains["flood"]
    assert flood.status == "degraded"
    assert flood.score is None
    assert "unavailable" in (flood.note or "").lower()
    # The scorecard as a whole still returns.
    assert res.scoring_profile == "fct-v1"


@pytest.mark.asyncio
async def test_pending_domains_have_no_fabricated_score():
    ok = FloodResult(
        status=FloodStatus.OK, risk_class="Low", risk_score=0.3, normalised=0.8,
        factors={}, model_version="ggis-fw-2.3", data_currency="2026-06-30", confidence="high",
    )
    res = await analyze(_req(), flood=_StubFlood(ok))  # type: ignore[arg-type]
    assert res.domains["amenities"].status == "pending"
    assert res.domains["amenities"].score is None


def _ok_flood() -> FloodResult:
    return FloodResult(
        status=FloodStatus.OK, risk_class="Low", risk_score=0.3, normalised=0.8,
        factors={}, model_version="ggis-fw-2.3", data_currency="2026-06-30", confidence="high",
    )


@pytest.mark.asyncio
async def test_scorecard_stamped_with_registry_versions():
    versions = {"poi": "2026.07.1", "roads": "2026.07.1", "dem": "2026.07.1"}
    res = await analyze(_req(), flood=_StubFlood(_ok_flood()), versions=versions)  # type: ignore[arg-type]
    # Registry versions are carried through, plus the live hazard version.
    assert res.layer_versions["poi"] == "2026.07.1"
    assert res.layer_versions["roads"] == "2026.07.1"
    assert res.layer_versions["hazard"] == "ggis-fw-2.3"


@pytest.mark.asyncio
async def test_second_request_served_from_cache_without_recompute():
    flood = _StubFlood(_ok_flood())
    cache = _FakeCache()
    versions = {"poi": "2026.07.1"}

    first = await analyze(_req(), flood=flood, versions=versions, cache=cache)  # type: ignore[arg-type]
    assert first.cached is False
    assert flood.calls == 1

    second = await analyze(_req(), flood=flood, versions=versions, cache=cache)  # type: ignore[arg-type]
    assert second.cached is True
    assert flood.calls == 1  # no second GGIS call — served from cache
    assert second.domains["flood"].score == first.domains["flood"].score


@pytest.mark.asyncio
async def test_layer_bump_changes_key_and_forces_recompute():
    flood = _StubFlood(_ok_flood())
    cache = _FakeCache()

    await analyze(_req(), flood=flood, versions={"poi": "2026.07.1"}, cache=cache)  # type: ignore[arg-type]
    assert flood.calls == 1

    # A layer bump changes the versions -> new cache key -> recompute.
    await analyze(_req(), flood=flood, versions={"poi": "2026.07.2"}, cache=cache)  # type: ignore[arg-type]
    assert flood.calls == 2

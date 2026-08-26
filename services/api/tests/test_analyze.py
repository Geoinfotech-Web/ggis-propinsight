"""Unit tests for the scorecard fan-out and GGIS graceful degradation (TDD §5.3)."""
from __future__ import annotations

import pytest

from app.flood.client import FloodResult, FloodStatus
from app.location_intelligence.schemas import AnalyzeRequest, DomainResult, GeoJSONGeometry
from app.location_intelligence.service import analyze


class _StubFlood:
    """Stubs the GGIS client so tests don't hit the network."""

    def __init__(self, result: FloodResult) -> None:
        self._result = result
        self.data_mode = result.data_mode
        self.calls = 0
        self.history_calls = 0
        self.meta_calls = 0

    async def risk(self, geometry, last_known=None):  # noqa: ANN001
        self.calls += 1
        return self._result

    async def history(self, lon=None, lat=None):  # noqa: ANN001
        self.history_calls += 1
        return [{"date": "2025-09-14", "severity": "moderate", "source": "Sentinel-1"}]

    async def meta(self):  # noqa: ANN201
        self.meta_calls += 1
        return {"model_version": self._result.model_version}


class _FakeCache:
    """In-memory stand-in for ScorecardCache with the same interface."""

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    @staticmethod
    def make_key(  # noqa: ANN001
        profile, geohash8, layer_versions, radius_m=5_000, flood_data_mode="mock"
    ):
        import json

        return (
            f"{profile}:{geohash8}:{radius_m}:{flood_data_mode}:"
            f"{json.dumps(layer_versions, sort_keys=True)}"
        )

    async def get(self, key):  # noqa: ANN001
        return self.store.get(key)

    async def set(self, key, value):  # noqa: ANN001
        self.store[key] = value


class _StubCoverage:
    async def lookup(self, lon, lat):  # noqa: ANN001
        return {
            "providers": [
                {
                    "provider": "MTN",
                    "generation": "5G",
                    "available": "yes",
                    "quality": "good",
                },
                {
                    "provider": "Airtel",
                    "generation": "5G",
                    "available": "no",
                    "quality": "unknown",
                },
            ],
            "providers_checked": 2,
            "providers_with_5g": ["MTN"],
            "available_count": 1,
            "connectivity_read": "Some 5G availability",
            "source": "Enext Wireless EMetrics",
            "source_url": "https://metrics.enextwireless.com/",
            "checked_at": "2026-08-26T11:00:00Z",
        }


def _req() -> AnalyzeRequest:
    return AnalyzeRequest(geometry=GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634]))


@pytest.mark.asyncio
async def test_analyze_returns_consumer_domains_for_buyer():
    ok = FloodResult(
        status=FloodStatus.OK, risk_class="High", risk_score=0.78, normalised=0.2,
        factors={"elevation_m": 342.1}, model_version="ggis-fw-2.3",
        data_currency="2026-06-30", confidence="high",
    )
    res = await analyze(_req(), flood=_StubFlood(ok))  # type: ignore[arg-type]
    assert set(res.domains) == {
        "flood", "security", "amenities", "accessibility",
        "market", "livability",
    }
    assert "feasibility" not in res.domains
    assert "feasibility" not in res.domain_priority
    assert "tenure" not in res.domains
    assert "tenure" not in res.domain_priority
    assert res.summary is not None
    assert "buying a home" in res.summary.lower()
    assert res.domains["flood"].score == 78.0
    assert res.domains["flood"].score_direction == "higher_is_worse"
    assert res.domains["flood"].rating == "High flood risk"
    assert res.domains["flood"].included_in_fit is True
    assert res.domains["flood"].status == "ok"
    assert res.layer_versions["hazard"] == "ggis-fw-2.3"
    assert "history_events" in res.domains["flood"].evidence
    assert res.analysis_radius_m == 5_000


def test_analyze_request_validates_radius_bounds():
    geometry = GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634])
    assert AnalyzeRequest(geometry=geometry, radius_m=5_000).radius_m == 5_000
    assert AnalyzeRequest(geometry=geometry, radius_m=20_000).radius_m == 20_000
    with pytest.raises(ValueError):
        AnalyzeRequest(geometry=geometry, radius_m=4_999)
    with pytest.raises(ValueError):
        AnalyzeRequest(geometry=geometry, radius_m=20_001)


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
    assert res.scoring_profile == "home_buyer"
    assert res.persona is not None
    assert res.persona.key == "home_buyer"
    assert res.domain_priority[0] == "flood"


@pytest.mark.asyncio
async def test_pending_domains_have_no_fabricated_score():
    ok = FloodResult(
        status=FloodStatus.OK, risk_class="Low", risk_score=0.3, normalised=0.8,
        factors={}, model_version="ggis-fw-2.3", data_currency="2026-06-30", confidence="high",
    )
    res = await analyze(_req(), flood=_StubFlood(ok))  # type: ignore[arg-type]
    assert res.domains["amenities"].status == "pending"
    assert res.domains["amenities"].score is None
    assert res.domains["amenities"].included_in_fit is False
    assert "poi" in (res.domains["amenities"].note or "")


def _ok_flood() -> FloodResult:
    return FloodResult(
        status=FloodStatus.OK, risk_class="Low", risk_score=0.3, normalised=0.8,
        factors={}, model_version="ggis-fw-2.3", data_currency="2026-06-30", confidence="high",
    )


@pytest.mark.parametrize(
    ("risk_class", "risk_score", "expected"),
    [
        ("Very Low", 0.1, 10.0),
        ("Low", 0.3, 30.0),
        ("Moderate", 0.5, 50.0),
        ("High", 0.78, 78.0),
        ("Very High", 0.92, 92.0),
    ],
)
@pytest.mark.asyncio
async def test_flood_preserves_ggis_risk_class_and_hazard_score(
    risk_class, risk_score, expected  # noqa: ANN001
):
    flood = FloodResult(
        status=FloodStatus.OK,
        risk_class=risk_class,
        risk_score=risk_score,
        normalised=1.0 - risk_score,
        factors={},
        model_version="ggis-fw-2.3",
        data_currency="2026-06-30",
        confidence="high",
    )
    res = await analyze(_req(), flood=_StubFlood(flood))  # type: ignore[arg-type]
    result = res.domains["flood"]
    assert result.score == expected
    assert result.rating == f"{risk_class} flood risk"
    assert result.score_direction == "higher_is_worse"


@pytest.mark.parametrize("risk_score", [None, -0.1, 1.1, float("inf"), float("nan")])
@pytest.mark.asyncio
async def test_invalid_flood_hazard_score_is_not_invented(risk_score):  # noqa: ANN001
    flood = FloodResult(
        status=FloodStatus.OK,
        risk_class="Low",
        risk_score=risk_score,
        normalised=0.8,
        factors={},
        model_version="ggis-fw-2.3",
        data_currency="2026-06-30",
        confidence="high",
    )
    res = await analyze(_req(), flood=_StubFlood(flood))  # type: ignore[arg-type]
    result = res.domains["flood"]
    assert result.score is None
    assert result.status == "degraded"
    assert result.included_in_fit is False


@pytest.mark.asyncio
async def test_live_ggis_class_produces_disclosed_propinsight_hazard_index():
    flood = FloodResult(
        status=FloodStatus.OK,
        risk_class="Moderate",
        risk_score=None,
        normalised=None,
        factors={"hazard_index_eligible": True, "susceptibility_class": 2},
        model_version="developer-api-1.0.0",
        data_currency="2026-08-13T14:25:05Z",
        confidence="Medium",
        data_mode="live",
    )
    result = (await analyze(_req(), flood=_StubFlood(flood))).domains["flood"]  # type: ignore[arg-type]

    assert result.score == 50.0
    assert result.rating == "Moderate flood risk"
    assert result.status == "ok"
    assert result.included_in_fit is True
    assert result.evidence["hazard_index"] == 50.0
    assert "risk_score" not in result.evidence
    assert "hazard_index_source" not in result.evidence
    assert "hazard_index_method" not in result.evidence
    assert "hazard_index_eligible" not in result.evidence
    assert "Lower hazard values are safer" in (result.note or "")


@pytest.mark.asyncio
async def test_mock_flood_is_demo_and_excluded_from_report_fit_and_highlights(monkeypatch):
    captured: dict[str, float | None] = {}

    async def fake_feasibility(session, lon, lat, versions, flood_normalised):  # noqa: ANN001
        captured["flood_normalised"] = flood_normalised
        return DomainResult(score=80.0, confidence="Medium")

    monkeypatch.setattr(
        "app.location_intelligence.service._score_feasibility",
        fake_feasibility,
    )
    demo = FloodResult(
        status=FloodStatus.OK,
        risk_class="High",
        risk_score=0.78,
        normalised=0.22,
        factors={},
        model_version="ggis-fw-2.3",
        data_currency="2026-06-30",
        confidence="high",
        data_mode="mock",
    )
    req = AnalyzeRequest(
        geometry=GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634]),
        profile="developer",
    )
    res = await analyze(req, flood=_StubFlood(demo))  # type: ignore[arg-type]
    result = res.domains["flood"]
    assert result.status == "demo"
    assert result.score == 78.0
    assert result.included_in_fit is False
    assert captured["flood_normalised"] is None
    assert all(item.domain != "flood" for item in res.highlights)


@pytest.mark.asyncio
async def test_cache_separates_live_and_mock_flood_modes():
    cache = _FakeCache()
    live = _StubFlood(_ok_flood())
    demo_result = _ok_flood()
    demo_result.data_mode = "mock"
    demo = _StubFlood(demo_result)

    await analyze(_req(), flood=live, cache=cache)  # type: ignore[arg-type]
    await analyze(_req(), flood=demo, cache=cache)  # type: ignore[arg-type]

    assert live.calls == 1
    assert demo.calls == 1
    assert len(cache.store) == 2


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


@pytest.mark.asyncio
async def test_radius_change_uses_a_separate_cache_entry():
    flood = _StubFlood(_ok_flood())
    cache = _FakeCache()
    versions = {"poi": "2026.07.1"}
    geometry = GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634])

    await analyze(
        AnalyzeRequest(geometry=geometry, radius_m=5_000),
        flood=flood,
        versions=versions,
        cache=cache,
    )  # type: ignore[arg-type]
    await analyze(
        AnalyzeRequest(geometry=geometry, radius_m=10_000),
        flood=flood,
        versions=versions,
        cache=cache,
    )  # type: ignore[arg-type]

    assert flood.calls == 2
    assert len(cache.store) == 2


@pytest.mark.asyncio
async def test_live_flood_model_change_invalidates_cache_without_registry_bump():
    flood = _StubFlood(_ok_flood())
    cache = _FakeCache()
    versions = {"poi": "2026.07.1", "hazard": "unpublished"}

    first = await analyze(_req(), flood=flood, versions=versions, cache=cache)  # type: ignore[arg-type]
    assert first.layer_versions["hazard"] == "ggis-fw-2.3"
    assert flood.calls == 1

    flood._result = FloodResult(
        status=FloodStatus.OK,
        risk_class="High",
        risk_score=0.8,
        normalised=0.2,
        factors={},
        model_version="ggis-fw-2.4",
        data_currency="2026-08-04",
        confidence="high",
    )
    second = await analyze(_req(), flood=flood, versions=versions, cache=cache)  # type: ignore[arg-type]

    assert second.cached is False
    assert second.layer_versions["hazard"] == "ggis-fw-2.4"
    assert flood.calls == 2


@pytest.mark.asyncio
async def test_analyze_investor_profile_sets_persona_and_priority():
    req = AnalyzeRequest(
        geometry=GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634]),
        profile="investor",
    )
    res = await analyze(req, flood=_StubFlood(_ok_flood()))  # type: ignore[arg-type]
    assert res.scoring_profile == "investor"
    assert res.persona is not None
    assert res.persona.key == "investor"
    assert res.persona.label == "Investor"
    assert res.domain_priority[0] == "market"
    assert "feasibility" in res.domains
    assert "feasibility" in res.domain_priority
    assert res.fit_score is not None  # at least flood is scored


@pytest.mark.asyncio
async def test_analyze_enriches_isp_amenity_with_network_coverage():
    res = await analyze(
        _req(),
        flood=_StubFlood(_ok_flood()),  # type: ignore[arg-type]
        network_coverage=_StubCoverage(),  # type: ignore[arg-type]
    )

    isp = res.domains["amenities"].evidence["isp"]
    assert isinstance(isp, dict)
    assert isp["network_coverage"]["providers_checked"] == 2
    assert isp["connectivity_read"] == "Some 5G availability"
    assert "network_coverage" not in res.domains["amenities"].evidence
    livability = res.domains.get("livability")
    if livability is not None:
        assert "connectivity_read" not in livability.evidence
        assert "network_coverage" not in livability.evidence


@pytest.mark.asyncio
async def test_tenant_excludes_planning_and_feasibility_from_report():
    req = AnalyzeRequest(
        geometry=GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634]),
        profile="tenant",
    )
    res = await analyze(req, flood=_StubFlood(_ok_flood()))  # type: ignore[arg-type]
    assert "feasibility" not in res.domains
    assert "feasibility" not in res.domain_priority
    assert "tenure" not in res.domains
    assert "tenure" not in res.domain_priority
    assert res.summary is not None
    assert "rent" in res.summary.lower()


@pytest.mark.asyncio
async def test_developer_includes_feasibility_leading_priority():
    req = AnalyzeRequest(
        geometry=GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634]),
        profile="developer",
    )
    res = await analyze(req, flood=_StubFlood(_ok_flood()))  # type: ignore[arg-type]
    assert "feasibility" in res.domains
    assert res.domain_priority[0] == "feasibility"


@pytest.mark.asyncio
async def test_legacy_fct_v1_profile_resolves_to_home_buyer():
    req = AnalyzeRequest(
        geometry=GeoJSONGeometry(type="Point", coordinates=[7.3986, 8.9634]),
        profile="fct-v1",
    )
    res = await analyze(req, flood=_StubFlood(_ok_flood()))  # type: ignore[arg-type]
    assert res.scoring_profile == "home_buyer"
    assert res.persona is not None
    assert res.persona.key == "home_buyer"

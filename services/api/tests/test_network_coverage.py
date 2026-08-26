from __future__ import annotations

import httpx
import pytest

from app.location_intelligence.network_coverage import EnextNetworkCoverageClient


@pytest.mark.asyncio
async def test_network_coverage_normalises_provider_results(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        layer = request.url.params["typeName"]
        if layer == "enextlog:mtn_5g_min":
            return httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {
                                "average_rsrq": -8.0,
                                "average_rsrp": -97.0,
                                "average_sinr": 18.0,
                                "point_counts": 14,
                                "data_source": "Enextlog",
                                "date": "2026-08-01",
                                "tp_date": "2026-08-03",
                            },
                        }
                    ],
                },
            )
        if layer == "enextlog:airtel_5g_min":
            return httpx.Response(
                200,
                json={"type": "FeatureCollection", "features": []},
            )
        raise AssertionError(f"unexpected layer {layer}")

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    coverage = await EnextNetworkCoverageClient(base_url="https://coverage.example").lookup(
        7.4871, 9.0435
    )

    assert coverage["providers_checked"] == 4
    assert coverage["providers_with_5g"] == ["MTN"]
    assert coverage["available_count"] == 1
    assert coverage["connectivity_read"] == "Some 5G availability"

    mtn = next(item for item in coverage["providers"] if item["provider"] == "MTN")
    assert mtn["available"] == "yes"
    assert mtn["quality"] == "good"
    assert mtn["metrics"]["point_counts"] == 14

    airtel = next(item for item in coverage["providers"] if item["provider"] == "Airtel")
    assert airtel["available"] == "no"

    glo = next(item for item in coverage["providers"] if item["provider"] == "Glo")
    assert glo["available"] == "unknown"
    assert "does not currently publish" in glo["note"]


@pytest.mark.asyncio
async def test_network_coverage_gracefully_marks_lookup_failures_unknown(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["typeName"] == "enextlog:mtn_5g_min":
            return httpx.Response(503, json={"detail": "down"})
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    coverage = await EnextNetworkCoverageClient(base_url="https://coverage.example").lookup(
        7.4871, 9.0435
    )

    mtn = next(item for item in coverage["providers"] if item["provider"] == "MTN")
    assert mtn["available"] == "unknown"
    assert "failed" in mtn["note"].lower()

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.location_intelligence.network_coverage import (
    PROVIDER_LAYERS,
    EnextNetworkCoverageClient,
)


def _feature_response() -> httpx.Response:
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


def _empty_response() -> httpx.Response:
    return httpx.Response(200, json={"type": "FeatureCollection", "features": []})


def _install_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:  # noqa: ANN001
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )


def test_provider_layers_cover_all_supported_generations_in_display_order():
    assert [
        (layer.generation, layer.provider, layer.layer_name) for layer in PROVIDER_LAYERS
    ] == [
        ("5G", "MTN", "mtn_5g_min"),
        ("5G", "Airtel", "airtel_5g_min"),
        ("5G", "Glo", None),
        ("5G", "9mobile", None),
        ("4G", "MTN", "mtn_pub_min"),
        ("4G", "Airtel", "airtel_pub_min"),
        ("4G", "Glo", "glo_pub_min"),
        ("4G", "9mobile", "nine_pub_min"),
        ("4G", "Smile", "smile_pub_min"),
        ("4G", "Spectranet", "spectranet_pub_min"),
    ]


@pytest.mark.asyncio
async def test_network_coverage_normalises_both_generations(monkeypatch):
    available_layers = {
        "enextlog:mtn_5g_min",
        "enextlog:mtn_pub_min",
        "enextlog:airtel_pub_min",
        "enextlog:glo_pub_min",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        layer = request.url.params["typeName"]
        return _feature_response() if layer in available_layers else _empty_response()

    _install_transport(monkeypatch, handler)
    coverage = await EnextNetworkCoverageClient(base_url="https://coverage.example").lookup(
        7.4871, 9.0435
    )

    assert coverage["providers_checked"] == 10
    assert coverage["providers_with_5g"] == ["MTN"]
    assert coverage["providers_with_4g"] == ["MTN", "Airtel", "Glo"]
    assert coverage["available_count"] == 1
    assert coverage["available_counts"] == {"4G": 3, "5G": 1}
    assert coverage["connectivity_read"] == (
        "5G available from MTN; supporting 4G / LTE available from MTN, Airtel, Glo"
    )
    assert [
        (item["generation"], item["provider"]) for item in coverage["providers"]
    ] == [(layer.generation, layer.provider) for layer in PROVIDER_LAYERS]

    mtn_5g = next(
        item
        for item in coverage["providers"]
        if item["provider"] == "MTN" and item["generation"] == "5G"
    )
    assert mtn_5g["available"] == "yes"
    assert mtn_5g["quality"] == "good"
    assert mtn_5g["metrics"]["point_counts"] == 14

    airtel_5g = next(
        item
        for item in coverage["providers"]
        if item["provider"] == "Airtel" and item["generation"] == "5G"
    )
    assert airtel_5g["available"] == "no"

    glo_5g = next(
        item
        for item in coverage["providers"]
        if item["provider"] == "Glo" and item["generation"] == "5G"
    )
    assert glo_5g["available"] == "unknown"
    assert "does not currently publish" in glo_5g["note"]


@pytest.mark.asyncio
async def test_confirmed_empty_layers_report_no_published_evidence(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return _empty_response()

    _install_transport(monkeypatch, handler)
    coverage = await EnextNetworkCoverageClient(base_url="https://coverage.example").lookup(
        7.4871, 9.0435
    )

    assert coverage["providers_with_5g"] == []
    assert coverage["providers_with_4g"] == []
    assert coverage["available_counts"] == {"4G": 0, "5G": 0}
    assert coverage["connectivity_read"] == (
        "No published 4G/5G coverage evidence at this point"
    )


@pytest.mark.parametrize(
    ("available_layers", "expected_read"),
    [
        (
            {"enextlog:mtn_pub_min", "enextlog:airtel_pub_min"},
            "Broad multi-network 4G / LTE availability",
        ),
        (
            {"enextlog:mtn_pub_min"},
            "Limited 4G / LTE availability from MTN",
        ),
    ],
)
@pytest.mark.asyncio
async def test_4g_only_summaries_follow_availability_breadth(
    monkeypatch, available_layers, expected_read  # noqa: ANN001
):
    async def handler(request: httpx.Request) -> httpx.Response:
        return (
            _feature_response()
            if request.url.params["typeName"] in available_layers
            else _empty_response()
        )

    _install_transport(monkeypatch, handler)
    coverage = await EnextNetworkCoverageClient(base_url="https://coverage.example").lookup(
        7.4871, 9.0435
    )

    assert coverage["providers_with_5g"] == []
    assert coverage["connectivity_read"] == expected_read


@pytest.mark.asyncio
async def test_partial_failures_and_malformed_payloads_remain_unknown(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        layer = request.url.params["typeName"]
        if layer == "enextlog:mtn_5g_min":
            return httpx.Response(503, json={"detail": "down"})
        if layer == "enextlog:airtel_5g_min":
            return httpx.Response(200, json={"type": "FeatureCollection"})
        return _empty_response()

    _install_transport(monkeypatch, handler)
    coverage = await EnextNetworkCoverageClient(base_url="https://coverage.example").lookup(
        7.4871, 9.0435
    )

    mtn_5g = coverage["providers"][0]
    airtel_5g = coverage["providers"][1]
    assert mtn_5g["available"] == "unknown"
    assert airtel_5g["available"] == "unknown"
    assert "failed" in mtn_5g["note"].lower()
    assert "failed" in airtel_5g["note"].lower()
    assert coverage["connectivity_read"] == "Coverage unavailable"


@pytest.mark.asyncio
async def test_total_upstream_failure_reports_coverage_unavailable(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timed out", request=request)

    _install_transport(monkeypatch, handler)
    coverage = await EnextNetworkCoverageClient(base_url="https://coverage.example").lookup(
        7.4871, 9.0435
    )

    assert all(item["available"] == "unknown" for item in coverage["providers"])
    assert coverage["connectivity_read"] == "Coverage unavailable"


@pytest.mark.asyncio
async def test_queryable_layers_run_concurrently_through_one_client(monkeypatch):
    active = 0
    peak = 0
    requested_layers: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        requested_layers.append(request.url.params["typeName"])
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return _empty_response()

    _install_transport(monkeypatch, handler)
    await EnextNetworkCoverageClient(
        base_url="https://coverage.example", timeout_ms=100
    ).lookup(7.4871, 9.0435)

    assert peak == 8
    assert requested_layers == [
        f"enextlog:{layer.layer_name}" for layer in PROVIDER_LAYERS if layer.layer_name
    ]

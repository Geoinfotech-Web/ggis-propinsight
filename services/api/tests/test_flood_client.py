"""GGIS Flood Watch legacy and Developer API contract compatibility."""
from __future__ import annotations

import httpx
import pytest

from app.flood.client import GGISFloodClient


@pytest.mark.asyncio
async def test_developer_api_adapter_preserves_class_without_inventing_score(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"]
        if request.url.path == "/v1/flood/risk":
            return httpx.Response(404, json={"detail": "Not Found"})
        assert request.url.path == "/v1/location/site-assessment"
        assert request.url.params["radius_km"] == "10"
        return httpx.Response(
            200,
            json={
                "susceptibility": "Moderate",
                "susceptibility_class": 2,
                "zones_inside": [],
                "zones_nearby": [
                    {
                        "name": "Abuja",
                        "risk_tier": "Likely",
                        "risk_score": 0.55,
                        "distance_km": 6.22,
                    }
                ],
                "radius_km": 10,
                "generated_at": "2026-08-13T14:22:29Z",
            },
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    result = await GGISFloodClient(base_url="https://api.example").risk(
        {"type": "Point", "coordinates": [7.49748, 9.06087]}
    )

    assert result.risk_class == "Moderate"
    assert result.risk_score is None
    assert result.normalised is None
    assert result.factors["susceptibility_class"] == 2
    assert result.factors["hazard_index_eligible"] is True
    assert result.factors["assessment_radius_km"] == 10
    assert result.factors["zones_nearby"][0]["risk_score"] == 0.55
    assert result.data_currency == "2026-08-13T14:22:29Z"


@pytest.mark.asyncio
async def test_developer_api_health_supplies_cache_version(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/meta/model":
            return httpx.Response(404, json={"detail": "Not Found"})
        return httpx.Response(
            200,
            json={"status": "ok", "version": "1.0.0", "time": "2026-08-13T14:25:05Z"},
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    meta = await GGISFloodClient(base_url="https://api.example").meta()

    assert meta["model_version"] == "developer-api-1.0.0"
    assert meta["data_currency"] == "2026-08-13T14:25:05Z"

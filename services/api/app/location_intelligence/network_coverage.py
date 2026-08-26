"""4G and 5G mobile coverage evidence via Enext Wireless GeoServer."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings

settings = get_settings()

SOURCE_NAME = "Enext Wireless EMetrics"
SOURCE_URL = "https://metrics.enextwireless.com/"
WFS_PATH = "/enextlog/ows"


@dataclass(frozen=True)
class ProviderLayer:
    provider: str
    generation: str
    layer_name: str | None
    note: str | None = None


PROVIDER_LAYERS: tuple[ProviderLayer, ...] = (
    ProviderLayer("MTN", "5G", "mtn_5g_min"),
    ProviderLayer("Airtel", "5G", "airtel_5g_min"),
    ProviderLayer(
        "Glo",
        "5G",
        None,
        "The selected source does not currently publish a dedicated Glo 5G layer.",
    ),
    ProviderLayer(
        "9mobile",
        "5G",
        None,
        "The selected source does not currently publish a dedicated 9mobile 5G layer.",
    ),
    ProviderLayer("MTN", "4G", "mtn_pub_min"),
    ProviderLayer("Airtel", "4G", "airtel_pub_min"),
    ProviderLayer("Glo", "4G", "glo_pub_min"),
    ProviderLayer("9mobile", "4G", "nine_pub_min"),
    ProviderLayer("Smile", "4G", "smile_pub_min"),
    ProviderLayer("Spectranet", "4G", "spectranet_pub_min"),
)


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalise_quality(value: str | None) -> str:
    if not value:
        return "unknown"
    quality = value.strip().lower()
    return (
        quality
        if quality in {"excellent", "good", "fair", "usable", "poor"}
        else "unknown"
    )


def _quality_from_metrics(properties: dict[str, Any]) -> str:
    rsrq = properties.get("average_rsrq")
    sinr = properties.get("average_sinr")
    rsrp = properties.get("average_rsrp")
    if (
        isinstance(rsrq, (int, float))
        and -7 <= rsrq < 0
        and isinstance(sinr, (int, float))
        and sinr > 20
    ):
        return "excellent"
    if (
        isinstance(rsrq, (int, float))
        and -12 < rsrq < 0
        and isinstance(sinr, (int, float))
        and sinr > 10
    ):
        return "good"
    if isinstance(rsrq, (int, float)) and -15 < rsrq <= -12 and (
        sinr is None or (isinstance(sinr, (int, float)) and sinr >= 2)
    ):
        return "fair"
    if isinstance(rsrq, (int, float)) and rsrq <= -15 and (
        (sinr is None and isinstance(rsrp, (int, float)) and rsrp > -118)
        or (isinstance(sinr, (int, float)) and sinr >= -5)
    ):
        return "usable"
    if isinstance(rsrp, (int, float)) and rsrp < -118:
        return "poor"
    return "unknown"


class EnextNetworkCoverageClient:
    def __init__(self, base_url: str | None = None, timeout_ms: int | None = None) -> None:
        self.base_url = (base_url or settings.enext_coverage_base_url).rstrip("/")
        self.timeout = (timeout_ms or settings.enext_coverage_timeout_ms) / 1000.0

    async def _query_provider(
        self,
        client: httpx.AsyncClient,
        layer: ProviderLayer,
        lon: float,
        lat: float,
        checked_at: str,
    ) -> dict[str, Any]:
        base = {
            "provider": layer.provider,
            "generation": layer.generation,
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "checked_at": checked_at,
            "source_layer": layer.layer_name,
        }
        if layer.layer_name is None:
            return {
                **base,
                "available": "unknown",
                "quality": "unknown",
                "note": layer.note,
            }

        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": f"enextlog:{layer.layer_name}",
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "CQL_FILTER": f"INTERSECTS(geom,POINT({lon} {lat}))",
        }
        response = await client.get(f"{self.base_url}{WFS_PATH}?{urlencode(params)}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Coverage response was not a GeoJSON object")
        features = payload.get("features")
        if not isinstance(features, list):
            raise ValueError("Coverage response did not contain a feature collection")
        if not features:
            return {
                **base,
                "available": "no",
                "quality": "unknown",
                "note": (
                    f"No {layer.provider} {layer.generation} coverage polygon covered "
                    "this point."
                ),
            }
        if not isinstance(features[0], dict) or not isinstance(
            features[0].get("properties"), dict
        ):
            raise ValueError("Coverage feature did not contain valid properties")
        props = features[0]["properties"]
        return {
            **base,
            "available": "yes",
            "quality": _quality_from_metrics(props),
            "metrics": {
                "average_rsrp": props.get("average_rsrp"),
                "average_rsrq": props.get("average_rsrq"),
                "average_sinr": props.get("average_sinr"),
                "point_counts": props.get("point_counts"),
                "data_source": props.get("data_source"),
                "rf_updated_at": props.get("date"),
                "tp_updated_at": props.get("tp_date"),
            },
        }

    async def lookup(self, lon: float, lat: float) -> dict[str, Any]:
        checked_at = _iso_now()

        async def query_provider(
            client: httpx.AsyncClient, provider: ProviderLayer
        ) -> dict[str, Any]:
            try:
                return await self._query_provider(client, provider, lon, lat, checked_at)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                return {
                    "provider": provider.provider,
                    "generation": provider.generation,
                    "available": "unknown",
                    "quality": "unknown",
                    "note": f"Coverage lookup failed: {exc}",
                    "source": SOURCE_NAME,
                    "source_url": SOURCE_URL,
                    "source_layer": provider.layer_name,
                    "checked_at": checked_at,
                }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            providers = list(
                await asyncio.gather(
                    *(query_provider(client, provider) for provider in PROVIDER_LAYERS)
                )
            )

        providers_with_5g = [
            row["provider"]
            for row in providers
            if row.get("generation") == "5G" and row.get("available") == "yes"
        ]
        providers_with_4g = [
            row["provider"]
            for row in providers
            if row.get("generation") == "4G" and row.get("available") == "yes"
        ]
        available_count = len(providers_with_5g)
        if providers_with_5g:
            connectivity_read = f"5G available from {', '.join(providers_with_5g)}"
            if providers_with_4g:
                connectivity_read += (
                    f"; supporting 4G / LTE available from {', '.join(providers_with_4g)}"
                )
        elif len(providers_with_4g) >= 2:
            connectivity_read = "Broad multi-network 4G / LTE availability"
        elif len(providers_with_4g) == 1:
            connectivity_read = f"Limited 4G / LTE availability from {providers_with_4g[0]}"
        else:
            queryable = [row for row in providers if row.get("source_layer") is not None]
            confirmed_empty_only = bool(queryable) and all(
                row.get("available") == "no" for row in queryable
            )
            connectivity_read = (
                "No published 4G/5G coverage evidence at this point"
                if confirmed_empty_only
                else "Coverage unavailable"
            )

        return {
            "providers": providers,
            "providers_checked": len(providers),
            "providers_with_5g": providers_with_5g,
            "providers_with_4g": providers_with_4g,
            "available_count": available_count,
            "available_counts": {
                "4G": len(providers_with_4g),
                "5G": len(providers_with_5g),
            },
            "connectivity_read": connectivity_read,
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "checked_at": checked_at,
        }


_client: EnextNetworkCoverageClient | None = None


def get_network_coverage_client() -> EnextNetworkCoverageClient:
    global _client
    if _client is None:
        _client = EnextNetworkCoverageClient()
    return _client

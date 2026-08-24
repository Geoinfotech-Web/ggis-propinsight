"""Client for the GGIS Flood Watch service API (TDD §5).

Contract implemented:
  POST /v1/flood/risk                  -> risk class + factors + model version
  GET  /v1/flood/history               -> observed inundation events
  POST /v1/flood/alerts/subscriptions  -> register webhook + AOI
  GET  /v1/tiles/hazard/{z}/{x}/{y}    -> hazard tiles (mirrored by ETL)
  GET  /v1/meta/model                  -> model version + coverage

Auth: service-to-service API key with HMAC request signing, over TLS.

Integration rules (TDD §5.3):
  * AIA never re-derives flood risk locally.
  * If GGIS is unreachable, callers receive a DEGRADED result carrying the last
    known class (if any) clearly timestamped — the scorecard still returns.
  * model_version and data_currency from GGIS are surfaced verbatim downstream.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()

class FloodStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"  # GGIS unreachable/slow; last-known or unavailable


@dataclass
class FloodResult:
    status: FloodStatus
    risk_class: str | None
    risk_score: float | None            # GGIS 0..1 hazard score (raw)
    normalised: float | None            # inverted [0,1] for the scoring engine
    factors: dict[str, Any]
    model_version: str | None
    data_currency: str | None
    confidence: str | None
    last_event: dict[str, Any] | None = None
    history_events: list[dict[str, Any]] = field(default_factory=list)
    stale: bool = False                 # True when served from cache during degradation
    message: str | None = None
    data_mode: str = "live"


def validated_risk_score(value: Any) -> float | None:
    """Return the authoritative GGIS 0..1 hazard score when it is usable."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    score = float(value)
    if not math.isfinite(score) or score < 0.0 or score > 1.0:
        return None
    return score


def _sign(method: str, path: str, body: bytes, ts: str) -> str:
    """HMAC-SHA256 over `method\\npath\\nts\\nsha256(body)` (service-to-service signing)."""
    body_hash = hashlib.sha256(body).hexdigest()
    payload = f"{method}\n{path}\n{ts}\n{body_hash}".encode()
    return hmac.new(settings.ggis_flood_hmac_secret.encode(), payload, hashlib.sha256).hexdigest()


def _headers(method: str, path: str, body: bytes) -> dict[str, str]:
    ts = str(int(time.time()))
    return {
        "X-API-Key": settings.ggis_flood_api_key,
        "X-GGIS-Key": settings.ggis_flood_api_key,
        "X-GGIS-Timestamp": ts,
        "X-GGIS-Signature": _sign(method, path, body, ts),
        "Content-Type": "application/json",
    }


class GGISFloodClient:
    def __init__(self, base_url: str | None = None, timeout_ms: int | None = None) -> None:
        self.base_url = (base_url or settings.ggis_flood_base_url).rstrip("/")
        self.timeout = (timeout_ms or settings.ggis_flood_timeout_ms) / 1000.0
        self.data_mode = settings.ggis_flood_data_mode
        self._contract: str | None = None
        self._model_version: str | None = None

    @staticmethod
    def _point(geometry: dict[str, Any]) -> tuple[float, float] | None:
        coordinates = geometry.get("coordinates")
        if geometry.get("type") == "Point" and isinstance(coordinates, list):
            if len(coordinates) >= 2:
                return float(coordinates[0]), float(coordinates[1])
        if geometry.get("type") == "Polygon" and isinstance(coordinates, list):
            ring = coordinates[0] if coordinates else []
            if isinstance(ring, list) and ring:
                points = [point for point in ring if isinstance(point, list) and len(point) >= 2]
                if points:
                    return (
                        sum(float(point[0]) for point in points) / len(points),
                        sum(float(point[1]) for point in points) / len(points),
                    )
        return None

    async def _developer_risk(self, geometry: dict[str, Any]) -> FloodResult:
        point = self._point(geometry)
        if point is None:
            return self._degrade(None, "GGIS site assessment requires a valid point")
        lon, lat = point
        path = "/v1/location/site-assessment"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                params={"lon": lon, "lat": lat, "radius_km": 10},
                headers=_headers("GET", path, b""),
            )
            response.raise_for_status()
            data = response.json()
        self._contract = "developer"
        risk_class = data.get("susceptibility")
        risk_score = validated_risk_score(data.get("risk_score"))
        generated_at = data.get("generated_at")
        factors = {
            "susceptibility_class": data.get("susceptibility_class"),
            "hazard_index_eligible": True,
            "zones_inside": data.get("zones_inside", []),
            "zones_nearby": data.get("zones_nearby", []),
            "assessment_radius_km": data.get("radius_km"),
        }
        return FloodResult(
            status=FloodStatus.OK,
            risk_class=str(risk_class) if risk_class else None,
            risk_score=risk_score,
            normalised=None if risk_score is None else 1.0 - risk_score,
            factors=factors,
            model_version=data.get("model_version") or self._model_version,
            data_currency=str(generated_at) if generated_at else None,
            confidence="Medium" if risk_class else "Low",
            message=(
                None
                if risk_score is not None
                else (
                    "Live GGIS classification is available; a numerical hazard score "
                    "was not published."
                )
            ),
            data_mode=self.data_mode,
        )

    async def risk(
        self, geometry: dict[str, Any], last_known: FloodResult | None = None
    ) -> FloodResult:
        """Live risk query. Falls back to `last_known` (timestamped) on failure."""
        if self._contract == "developer":
            try:
                return await self._developer_risk(geometry)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                return self._degrade(last_known, str(exc))

        path = "/v1/flood/risk"
        body = json.dumps({"geometry": geometry, "detail": "full"}).encode()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                resp = await c.post(
                    f"{self.base_url}{path}", content=body, headers=_headers("POST", path, body)
                )
                # Live GFW currently publishes developer site-assessment; treat
                # missing/broken legacy risk routes as a signal to use that path.
                if resp.status_code in {404, 405, 500, 501, 502, 503}:
                    try:
                        return await self._developer_risk(geometry)
                    except (httpx.HTTPError, ValueError, TypeError) as fallback_exc:
                        return self._degrade(
                            last_known,
                            f"legacy risk {resp.status_code}; site-assessment failed ({fallback_exc})",
                        )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            try:
                return await self._developer_risk(geometry)
            except (httpx.HTTPError, ValueError, TypeError):
                return self._degrade(last_known, str(exc))

        risk_class = data.get("risk_class")
        risk_score = validated_risk_score(data.get("risk_score"))
        last_event = data.get("last_event")
        if not isinstance(last_event, dict):
            last_event = None
        return FloodResult(
            status=FloodStatus.OK,
            risk_class=risk_class,
            risk_score=risk_score,
            normalised=None if risk_score is None else 1.0 - risk_score,
            factors=data.get("factors", {}),
            model_version=data.get("model_version"),
            data_currency=data.get("data_currency"),
            confidence=data.get("confidence"),
            last_event=last_event,
            data_mode=self.data_mode,
        )

    async def history(
        self, lon: float | None = None, lat: float | None = None
    ) -> list[dict[str, Any]]:
        """Observed inundation events near a point (Phase 1: global list from GGIS)."""
        if self._contract == "developer":
            return []
        path = "/v1/flood/history"
        params: dict[str, float] = {}
        if lon is not None and lat is not None:
            params = {"lon": lon, "lat": lat}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                resp = await c.get(
                    f"{self.base_url}{path}",
                    params=params or None,
                    headers=_headers("GET", path, b""),
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError):
            return []
        events = data.get("events", [])
        return events if isinstance(events, list) else []

    def _degrade(self, last_known: FloodResult | None, reason: str) -> FloodResult:
        if last_known is not None:
            return FloodResult(
                status=FloodStatus.DEGRADED,
                risk_class=last_known.risk_class,
                risk_score=last_known.risk_score,
                normalised=last_known.normalised,
                factors=last_known.factors,
                model_version=last_known.model_version,
                data_currency=last_known.data_currency,
                confidence="Low",
                last_event=last_known.last_event,
                history_events=list(last_known.history_events),
                stale=True,
                message=f"GGIS unreachable; serving last-known class. ({reason})",
                data_mode=last_known.data_mode,
            )
        return FloodResult(
            status=FloodStatus.DEGRADED,
            risk_class=None,
            risk_score=None,
            normalised=None,
            factors={},
            model_version=None,
            data_currency=None,
            confidence=None,
            stale=True,
            message=f"Flood domain temporarily unavailable. ({reason})",
            data_mode=self.data_mode,
        )

    async def meta(self) -> dict[str, Any]:
        path = "/v1/meta/model"
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.get(f"{self.base_url}{path}", headers=_headers("GET", path, b""))
            if resp.status_code in {404, 405, 500, 501, 502, 503}:
                health_path = "/v1/health"
                health = await c.get(
                    f"{self.base_url}{health_path}",
                    headers=_headers("GET", health_path, b""),
                )
                if health.status_code >= 400:
                    health.raise_for_status()
                data = health.json()
                version = data.get("version") if isinstance(data, dict) else None
                self._model_version = f"developer-api-{version}" if version else None
                self._contract = "developer"
                if isinstance(data, dict):
                    return {
                        **data,
                        "model_version": self._model_version,
                        "data_currency": data.get("time"),
                    }
                return data
            resp.raise_for_status()
            self._contract = "legacy"
            data = resp.json()
            if isinstance(data, dict) and data.get("model_version"):
                self._model_version = str(data["model_version"])
            return data


def get_flood_client() -> GGISFloodClient:
    return GGISFloodClient()

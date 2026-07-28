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
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()

# Map GGIS risk class -> normalised [0,1] domain input (inverted: high risk = low score).
RISK_CLASS_TO_SCORE: dict[str, float] = {
    "Very Low": 1.0,
    "Low": 0.8,
    "Moderate": 0.5,
    "High": 0.2,
    "Very High": 0.0,
}


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
    stale: bool = False                 # True when served from cache during degradation
    message: str | None = None


def _sign(method: str, path: str, body: bytes, ts: str) -> str:
    """HMAC-SHA256 over `method\\npath\\nts\\nsha256(body)` (service-to-service signing)."""
    body_hash = hashlib.sha256(body).hexdigest()
    payload = f"{method}\n{path}\n{ts}\n{body_hash}".encode()
    return hmac.new(settings.ggis_flood_hmac_secret.encode(), payload, hashlib.sha256).hexdigest()


def _headers(method: str, path: str, body: bytes) -> dict[str, str]:
    ts = str(int(time.time()))
    return {
        "X-GGIS-Key": settings.ggis_flood_api_key,
        "X-GGIS-Timestamp": ts,
        "X-GGIS-Signature": _sign(method, path, body, ts),
        "Content-Type": "application/json",
    }


class GGISFloodClient:
    def __init__(self, base_url: str | None = None, timeout_ms: int | None = None) -> None:
        self.base_url = (base_url or settings.ggis_flood_base_url).rstrip("/")
        self.timeout = (timeout_ms or settings.ggis_flood_timeout_ms) / 1000.0

    async def risk(
        self, geometry: dict[str, Any], last_known: FloodResult | None = None
    ) -> FloodResult:
        """Live risk query. Falls back to `last_known` (timestamped) on failure."""
        path = "/v1/flood/risk"
        body = json.dumps({"geometry": geometry, "detail": "full"}).encode()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                resp = await c.post(
                    f"{self.base_url}{path}", content=body, headers=_headers("POST", path, body)
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            return self._degrade(last_known, str(exc))

        risk_class = data.get("risk_class")
        return FloodResult(
            status=FloodStatus.OK,
            risk_class=risk_class,
            risk_score=data.get("risk_score"),
            normalised=RISK_CLASS_TO_SCORE.get(risk_class or "", None),
            factors=data.get("factors", {}),
            model_version=data.get("model_version"),
            data_currency=data.get("data_currency"),
            confidence=data.get("confidence"),
        )

    @staticmethod
    def _degrade(last_known: FloodResult | None, reason: str) -> FloodResult:
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
                stale=True,
                message=f"GGIS unreachable; serving last-known class. ({reason})",
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
        )

    async def meta(self) -> dict[str, Any]:
        path = "/v1/meta/model"
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.get(f"{self.base_url}{path}", headers=_headers("GET", path, b""))
            resp.raise_for_status()
            return resp.json()


def get_flood_client() -> GGISFloodClient:
    return GGISFloodClient()

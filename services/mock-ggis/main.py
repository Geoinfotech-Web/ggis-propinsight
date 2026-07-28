"""Mock GGIS Flood Watch service (TDD §5).

A stand-in for the real GGIS Flood Watch API so AIA development is never blocked
on the upstream service. Implements the §5.1 contract with deterministic,
coordinate-seeded responses. NOT a flood model — for local dev/testing only.

Run: uvicorn main:app --host 0.0.0.0 --port 9100
"""
from __future__ import annotations

import hashlib
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock GGIS Flood Watch", version="ggis-fw-2.3-mock")

_CLASSES = ["Very Low", "Low", "Moderate", "High", "Very High"]
_SCORES = {"Very Low": 0.1, "Low": 0.3, "Moderate": 0.5, "High": 0.78, "Very High": 0.92}


class RiskRequest(BaseModel):
    geometry: dict[str, Any]
    detail: str = "full"


def _seed(geometry: dict[str, Any]) -> int:
    coords = geometry.get("coordinates", [0, 0])
    while isinstance(coords, list) and coords and isinstance(coords[0], list):
        coords = coords[0]
    key = f"{coords}".encode()
    return int(hashlib.sha256(key).hexdigest(), 16)


@app.post("/v1/flood/risk")
def risk(req: RiskRequest) -> dict[str, Any]:
    s = _seed(req.geometry)
    risk_class = _CLASSES[s % len(_CLASSES)]
    return {
        "risk_class": risk_class,
        "risk_score": _SCORES[risk_class],
        "factors": {
            "elevation_m": 300 + (s % 200),
            "dist_to_drainage_m": s % 500,
            "flow_accumulation_pct": s % 100,
            "historical_inundation_events": s % 5,
        },
        "last_event": {"date": "2025-09-14", "severity": "moderate", "source": "Sentinel-1"},
        "model_version": "ggis-fw-2.3",
        "data_currency": "2026-06-30",
        "confidence": "high",
    }


@app.get("/v1/flood/history")
def history() -> dict[str, Any]:
    return {"events": [{"date": "2025-09-14", "severity": "moderate", "source": "Sentinel-1"}]}


@app.post("/v1/flood/alerts/subscriptions")
def subscribe() -> dict[str, Any]:
    return {"id": "sub_mock_1", "status": "active"}


@app.delete("/v1/flood/alerts/{sub_id}")
def unsubscribe(sub_id: str) -> dict[str, Any]:
    return {"id": sub_id, "status": "deleted"}


@app.get("/v1/meta/model")
def meta() -> dict[str, Any]:
    return {
        "model_version": "ggis-fw-2.3",
        "coverage_extent": "FCT (Abuja) pilot",
        "input_datasets": ["Sentinel-1 SAR", "Copernicus DEM", "NIHSA outlook"],
        "last_update": "2026-06-30",
    }

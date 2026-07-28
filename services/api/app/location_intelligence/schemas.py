"""Request/response models for the location intelligence API (TDD §7, Appendix A)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# The eight intelligence domains (Overview §3).
DOMAINS = (
    "flood",
    "security",
    "amenities",
    "accessibility",
    "tenure",
    "market",
    "livability",
    "feasibility",
)


class GeoJSONGeometry(BaseModel):
    type: Literal["Point", "Polygon"]
    coordinates: list[Any]


class AnalyzeRequest(BaseModel):
    geometry: GeoJSONGeometry
    profile: str = Field(default="fct-v1", description="Scoring profile key")


class DomainResult(BaseModel):
    score: float | None
    confidence: str
    status: Literal["ok", "degraded", "pending"] = "ok"
    evidence: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class LocationInfo(BaseModel):
    district: str | None = None
    state: str | None = None
    geohash8: str | None = None


class ScorecardResponse(BaseModel):
    location: LocationInfo
    domains: dict[str, DomainResult]
    layer_versions: dict[str, str] = Field(default_factory=dict)
    scoring_profile: str
    cached: bool = False

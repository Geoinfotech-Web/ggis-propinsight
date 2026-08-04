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
    profile: str = Field(
        default="home_buyer",
        description=(
            "Persona scoring profile: home_buyer|investor|tenant|developer "
            "(fct-v1 -> home_buyer)"
        ),
    )


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


class PersonaInfo(BaseModel):
    key: str
    label: str
    blurb: str


class ScorecardResponse(BaseModel):
    location: LocationInfo
    domains: dict[str, DomainResult]
    layer_versions: dict[str, str] = Field(default_factory=dict)
    scoring_profile: str
    cached: bool = False
    persona: PersonaInfo | None = None
    fit_score: float | None = None
    summary: str | None = None
    domain_priority: list[str] = Field(default_factory=list)

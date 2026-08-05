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


class LandUseInfo(BaseModel):
    category: str
    label: str
    name: str | None = None
    source_class: str | None = None
    source_subtype: str | None = None
    designation: str
    source: str
    source_url: str | None = None
    effective_date: str | None = None
    advisory: str


class LandCoverInfo(BaseModel):
    class_value: int
    category: str
    label: str
    designation: Literal["observed_land_cover"]
    source: str
    source_url: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    resolution_m: int
    advisory: str


class LocationInfo(BaseModel):
    district: str | None = None
    ward: str | None = None
    area_council: str | None = None
    state: str | None = None
    geohash8: str | None = None
    land_use: LandUseInfo | None = None
    land_cover: LandCoverInfo | None = None
    planning_status: Literal[
        "official", "mapped_reference", "observed_cover_only", "unmapped"
    ] = "unmapped"


class PersonaInfo(BaseModel):
    key: str
    label: str
    blurb: str


class ScorecardHighlight(BaseModel):
    domain: str
    title: str
    text: str
    tone: Literal["positive", "neutral", "caution"]


class ScorecardResponse(BaseModel):
    location: LocationInfo
    domains: dict[str, DomainResult]
    layer_versions: dict[str, str] = Field(default_factory=dict)
    scoring_profile: str
    cached: bool = False
    persona: PersonaInfo | None = None
    fit_score: float | None = None
    summary: str | None = None
    highlights: list[ScorecardHighlight] = Field(default_factory=list)
    domain_priority: list[str] = Field(default_factory=list)

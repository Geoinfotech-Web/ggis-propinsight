"""AIA v1 location endpoints (TDD §7)."""
from __future__ import annotations

from fastapi import APIRouter

from app.location_intelligence.schemas import AnalyzeRequest, ScorecardResponse
from app.location_intelligence.service import analyze

router = APIRouter(prefix="/v1/locations", tags=["locations"])


@router.post("/analyze", response_model=ScorecardResponse)
async def analyze_location(req: AnalyzeRequest) -> ScorecardResponse:
    """Point/polygon in → full eight-domain scorecard JSON (TDD Appendix A)."""
    return await analyze(req)

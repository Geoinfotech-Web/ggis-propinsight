"""AIA v1 location endpoints (TDD §7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import ScorecardCache, get_cache
from app.db import get_session
from app.location_intelligence.registry import current_layer_versions
from app.location_intelligence.schemas import AnalyzeRequest, ScorecardResponse
from app.location_intelligence.service import analyze

router = APIRouter(prefix="/v1/locations", tags=["locations"])


@router.post("/analyze", response_model=ScorecardResponse)
async def analyze_location(
    req: AnalyzeRequest,
    session: AsyncSession = Depends(get_session),
    cache: ScorecardCache = Depends(get_cache),
) -> ScorecardResponse:
    """Point/polygon in → full eight-domain scorecard JSON (TDD Appendix A).

    Reads current layer versions from `layer_registry` to stamp and cache the
    result (Redis, keyed by geohash8 + versions + profile).
    """
    versions = await current_layer_versions(session)
    return await analyze(req, versions=versions, cache=cache, session=session)

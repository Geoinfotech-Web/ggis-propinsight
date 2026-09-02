"""AIA v1 location endpoints (TDD §7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import ScorecardCache, get_cache
from app.db import get_session
from app.location_intelligence.land_cover import land_cover_meta, land_cover_tile
from app.location_intelligence.land_use import land_use_feature_collection
from app.location_intelligence.professional_3d import (
    building_feature_collection,
    vegetation_feature_collection,
)
from app.location_intelligence.registry import current_layer_versions
from app.location_intelligence.schemas import AnalyzeRequest, ScorecardResponse
from app.location_intelligence.service import analyze
from app.state_readiness import public_states, state_layer_versions

router = APIRouter(prefix="/v1/locations", tags=["locations"])


@router.get("/land-cover/meta")
async def observed_land_cover_meta(
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await land_cover_meta(session)


@router.get("/states")
async def states_for_selector(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Nigeria state selector/readiness for the public report flow."""
    return await public_states(session)


@router.get("/land-cover/tiles/{z}/{x}/{y}.png")
async def observed_land_cover_tile(
    z: int,
    x: int,
    y: int,
    session: AsyncSession = Depends(get_session),
):
    return await land_cover_tile(session, z, x, y)


@router.get("/land-use")
async def land_use_map(
    min_lon: float = Query(6.75, ge=-180, le=180),
    min_lat: float = Query(8.25, ge=-90, le=90),
    max_lon: float = Query(7.75, ge=-180, le=180),
    max_lat: float = Query(9.35, ge=-90, le=90),
    limit: int = Query(5_000, ge=1, le=5_000),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Published land-use polygons for map display (reference, not legal zoning)."""
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status_code=422, detail="bbox minimums must be below maximums")
    return await land_use_feature_collection(
        session,
        (min_lon, min_lat, max_lon, max_lat),
        limit=limit,
    )


@router.get("/3d/buildings")
async def professional_buildings(
    min_lon: float = Query(..., ge=-180, le=180),
    min_lat: float = Query(..., ge=-90, le=90),
    max_lon: float = Query(..., ge=-180, le=180),
    max_lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    limit: int = Query(10_000, ge=1, le=10_000),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await building_feature_collection(
        session, (min_lon, min_lat, max_lon, max_lat), (lon, lat), limit=limit
    )


@router.get("/3d/vegetation")
async def professional_vegetation(
    min_lon: float = Query(..., ge=-180, le=180),
    min_lat: float = Query(..., ge=-90, le=90),
    max_lon: float = Query(..., ge=-180, le=180),
    max_lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    limit: int = Query(3_000, ge=1, le=3_000),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await vegetation_feature_collection(
        session, (min_lon, min_lat, max_lon, max_lat), (lon, lat), limit=limit
    )


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
    effective_versions = await state_layer_versions(session, versions, req.state_code)
    return await analyze(req, versions=effective_versions, cache=cache, session=session)

"""FastAPI gateway — single app fronting all AIA services (TDD §4.2).

Versioned under /v1; breaking changes only via a new version.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.admin_gis import router as admin_router
from app.auth import bootstrap_admin_from_env, router as auth_router
from app.config import get_settings
from app.db import get_session
from app.flood.client import get_flood_client
from app.location_intelligence.readiness import readiness_rows
from app.location_intelligence.registry import current_layer_versions
from app.location_intelligence.router import router as locations_router

settings = get_settings()
logging.basicConfig(level=settings.aia_log_level)

app = FastAPI(
    title="GGIS PropInsight (AIA) API",
    version=__version__,
    description="Location intelligence API for the Nigerian property market with phased nationwide coverage.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1_024)

meta = APIRouter(tags=["meta"])


@meta.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "env": settings.aia_env}


@meta.get("/v1/meta/flood")
async def flood_meta() -> dict:
    """Surface the configured flood-data mode and upstream GGIS metadata."""
    try:
        return {
            "status": "ok",
            "data_mode": settings.ggis_flood_data_mode,
            "ggis": await get_flood_client().meta(),
        }
    except Exception as exc:  # noqa: BLE001 — degrade gracefully, never 500 the meta probe
        return {
            "status": "degraded",
            "data_mode": settings.ggis_flood_data_mode,
            "error": str(exc),
        }


@meta.get("/v1/meta/readiness")
async def domain_readiness(session: AsyncSession = Depends(get_session)) -> dict:
    """Phase 1 domain readiness vs published `layer_registry` versions."""
    versions = await current_layer_versions(session)
    return {
        "status": "ok",
        "layer_versions": versions,
        "domains": readiness_rows(versions),
    }


app.include_router(meta)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(locations_router)


@app.on_event("startup")
async def bootstrap_configured_admin() -> None:
    await bootstrap_admin_from_env()

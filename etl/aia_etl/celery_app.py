"""Celery application + beat schedule for the AIA ETL pipelines (TDD §4.6).

Refresh cycles:
  OSM roads & POIs ......... monthly
  GGIS flood hazard tiles .. per GGIS release + seasonal (nightly check here)
  DEM & terrain ............ one-time + on new UAV surveys (manual/triggered)
  Agency registries ........ quarterly
  Market samples ........... monthly
  Open land-use context .... monthly / per Overture release
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from aia_etl.config import get_settings

settings = get_settings()

app = Celery(
    "aia_etl",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "aia_etl.tasks.osm",
        "aia_etl.tasks.amenities",
        "aia_etl.tasks.dem",
        "aia_etl.tasks.flood_tiles",
        "aia_etl.tasks.market",
        "aia_etl.tasks.land_use",
        "aia_etl.tasks.boundaries",
        "aia_etl.tasks.land_cover",
        "aia_etl.tasks.official_land_use",
        "aia_etl.tasks.environment",
        "aia_etl.tasks.projects",
    ],
)

app.conf.update(
    task_track_started=True,
    task_time_limit=60 * 60,          # 1h hard cap for heavy geoprocessing
    task_soft_time_limit=55 * 60,
    worker_max_tasks_per_child=20,    # recycle workers to bound GDAL memory growth
    timezone="Africa/Lagos",
    enable_utc=True,
)

# Periodic schedule. Times are in the configured timezone (Africa/Lagos).
# Manual Phase 1 unlock order (see aia_etl.domain_deps.PHASE1_PIPELINE_PRIORITY):
#   1) refresh_osm  2) dem_from_gee  3) mirror_hazard_tiles
app.conf.beat_schedule = {
    "osm-monthly": {
        "task": "aia_etl.tasks.osm.refresh_osm",
        "schedule": crontab(minute=0, hour=2, day_of_month=1),
    },
    "flood-tiles-nightly-check": {
        "task": "aia_etl.tasks.flood_tiles.mirror_hazard_tiles",
        "schedule": crontab(minute=30, hour=1),
    },
    "market-monthly": {
        "task": "aia_etl.tasks.market.refresh_market_samples",
        "schedule": crontab(minute=0, hour=3, day_of_month=2),
    },
    "land-use-monthly": {
        "task": "aia_etl.tasks.land_use.refresh_land_use",
        "schedule": crontab(minute=30, hour=3, day_of_month=2),
    },
    "land-cover-monthly": {
        "task": "aia_etl.tasks.land_cover.refresh_land_cover",
        "schedule": crontab(minute=0, hour=4, day_of_month=2),
    },
    "environment-annual": {
        "task": "aia_etl.tasks.environment.refresh_environmental_metrics",
        "schedule": crontab(minute=0, hour=1, day_of_month=5, month_of_year=4),
    },
    "official-projects-weekly": {
        "task": "aia_etl.tasks.projects.refresh_development_projects",
        "schedule": crontab(minute=0, hour=5, day_of_week=1),
    },
}

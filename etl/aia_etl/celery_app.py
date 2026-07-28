"""Celery application + beat schedule for the AIA ETL pipelines (TDD §4.6).

Refresh cycles:
  OSM roads & POIs ......... monthly
  GGIS flood hazard tiles .. per GGIS release + seasonal (nightly check here)
  DEM & terrain ............ one-time + on new UAV surveys (manual/triggered)
  Agency registries ........ quarterly
  Market samples ........... monthly
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
        "aia_etl.tasks.dem",
        "aia_etl.tasks.flood_tiles",
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
        # Placeholder cadence; task lands in Phase 3.
        "task": "aia_etl.tasks.osm.noop",
        "schedule": crontab(minute=0, hour=3, day_of_month=2),
    },
}

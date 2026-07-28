"""GGIS PropInsight (AIA) — ETL & geoprocessing pipelines (TDD §4.6).

Celery-scheduled jobs that assemble and refresh the AIA data layers for the FCT
pilot. Every published layer bump changes its registry version and triggers a
cache-invalidation sweep of dependent scorecards (the `layer_version`
discipline — the backbone of cache correctness).
"""

__version__ = "0.1.0"

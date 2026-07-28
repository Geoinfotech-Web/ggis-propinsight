# ETL & Geoprocessing Pipeline

Python-based ETL for the AIA data layers (TDD §4.6). Celery + Redis for scheduling;
GDAL / rasterio / exactextract for raster analytics; QGIS-supported production workflows.

## Layers & refresh cycles

| Layer | Refresh | Pipeline summary |
|---|---|---|
| OSM roads & POIs | Monthly | Geofabrik Nigeria extract → `osm2pgsql` → QA rules → **layer_version bump** → OSRM/Valhalla graph rebuild |
| GGIS flood hazard tiles | Per GGIS release + seasonal | Harvest hazard rasters/vectors via GGIS API → COG conversion → TiTiler registration |
| DEM & terrain derivatives | One-time + on new UAV surveys | Slope, flow accumulation, TWI (GDAL/rasterio) |
| Agency facility registries | Quarterly | Geocode, dedup against OSM POIs, field-verification flags |
| Verified POIs (field) | Continuous | QField/ODK collection → admin review queue → publish |
| Market samples | Monthly | Geocode → outlier filter → spatial price surfaces (kriging/IDW) |

## `layer_version` discipline

Every published layer bump changes `layer_version` and triggers a Celery sweep that
invalidates dependent cached scores (see `scores.layer_versions`). This is the backbone
of cache correctness — implement it before wiring the first ETL job.

## Phase 1 priorities (FCT pilot)

1. OSM roads & POIs for FCT → PostGIS.
2. Copernicus/SRTM DEM → slope + flow accumulation + TWI → COG → TiTiler.
3. GGIS hazard tile mirror (COG) so map rendering survives GGIS downtime.

## Package layout (`aia_etl/`)

| Module | Responsibility |
|---|---|
| `layers.py` | The `layer_version` backbone: CalVer versioning, `bump_layer`, and the `sweep_stale_scores` cache-invalidation. **Built and tested first**, per the note above. |
| `celery_app.py` | Celery app + beat schedule for the §4.6 refresh cycles. |
| `poi_categories.py` | OSM tag → AIA `poi.category` mapping (school/hospital/water/…). |
| `qa.py` | QA-rule framework (geometry present, valid category, within-AOI bbox). |
| `tasks/osm.py` | `refresh_osm` — extract → clip → osm2pgsql → categorise → QA → publish → bump. |
| `tasks/dem.py` | `terrain_derivatives` — slope, flow accumulation, TWI COGs → bump `dem`. |
| `tasks/flood_tiles.py` | `mirror_hazard_tiles` — mirror GGIS hazard COGs on model-version change. |

The `layer_registry` table (Alembic migration `0002`) is the shared source of truth
for current layer versions; the API reads it to stamp scorecards, ETL bumps it on
publish.

## Run

```bash
# Local dev via the root compose stack (adds etl-worker + etl-beat):
docker compose up --build etl-worker etl-beat

# Trigger a pipeline manually (inside the worker container or a shell with deps):
celery -A aia_etl.celery_app call aia_etl.tasks.osm.refresh_osm
celery -A aia_etl.celery_app call aia_etl.tasks.flood_tiles.mirror_hazard_tiles
```

## Tests

Pure-logic tests (versioning, staleness, categorisation, QA) run without the geo
stack or a database:

```bash
cd etl
pip install pytest "sqlalchemy>=2.0"
python -m pytest -q
```

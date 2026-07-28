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

_Scaffolding for the ETL package lands here as Phase 1 data work begins._

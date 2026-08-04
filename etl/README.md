# ETL & Geoprocessing Pipeline

Python-based ETL for the AIA data layers (TDD §4.6). Celery + Redis for scheduling;
GDAL / rasterio / exactextract for raster analytics; QGIS-supported production workflows.

## Layers & refresh cycles

| Layer | Refresh | Pipeline summary |
|---|---|---|
| OSM roads & POIs | Monthly | Geofabrik Nigeria extract → `osm2pgsql` → QA rules → atomic canonical publish → **layer_version bump** → OSRM/Valhalla graph rebuild |
| GGIS flood hazard tiles | Per GGIS release + seasonal | Harvest hazard rasters/vectors via GGIS API → COG conversion → TiTiler registration |
| DEM & terrain derivatives | One-time + on new UAV surveys | Slope, flow accumulation, TWI (GDAL/rasterio) |
| Agency facility registries | Quarterly | Geocode, dedup against OSM POIs, field-verification flags |
| Verified POIs (field) | Continuous | QField/ODK collection → admin review queue → publish |
| Market samples | Monthly | Geocode → outlier filter → spatial price surfaces (kriging/IDW) |
| Open land-use context | Monthly / Overture release | Overture `base/land_use` polygons → stable product classes → atomic `land_use` publish; explicitly non-statutory |

## `layer_version` discipline

Every published layer bump changes `layer_version` and triggers a Celery sweep that
invalidates dependent cached scores (see `scores.layer_versions`). This is the backbone
of cache correctness — implement it before wiring the first ETL job.

## Phase 1 priorities (FCT pilot)

Domain readiness is gated by published `layer_registry` versions — see
`aia_etl/domain_deps.py` (single source of truth for domain → layer → task).

| Priority | Pipeline | Unlocks |
|---|---|---|
| 1 | `refresh_osm` (Geofabrik extract) | `amenities` (POI KNN), `accessibility` data |
| 2 | `dem_from_gee` / `terrain_derivatives` | `feasibility` terrain inputs (GEE IAM may block) |
| 3 | `mirror_hazard_tiles` | Map resilience if GGIS is down (flood scores stay live) |

1. OSM roads & POIs for FCT → PostGIS.
2. Copernicus/SRTM DEM → slope + flow accumulation + TWI → COG → TiTiler.
3. GGIS hazard tile mirror (COG) so map rendering survives GGIS downtime.

## Package layout (`aia_etl/`)

| Module | Responsibility |
|---|---|
| `domain_deps.py` | Domain → required layers → Celery tasks readiness map (Phase 1 unlock order). |
| `layers.py` | The `layer_version` backbone: CalVer versioning, `bump_layer`, and the `sweep_stale_scores` cache-invalidation. **Built and tested first**, per the note above. |
| `celery_app.py` | Celery app + beat schedule for the §4.6 refresh cycles. |
| `poi_categories.py` | OSM tag → AIA `poi.category` mapping (school/hospital/water/…). |
| `qa.py` | QA-rule framework (geometry present, valid category, within-AOI bbox). |
| `tasks/osm.py` | `refresh_osm` — extract → clip → osm2pgsql → categorise → QA → publish → bump. |
| `tasks/dem.py` | `terrain_derivatives` — slope, flow accumulation, TWI COGs → bump `dem`. |
| `tasks/flood_tiles.py` | `mirror_hazard_tiles` — mirror GGIS hazard COGs on model-version change. |
| `tasks/land_use.py` | `refresh_land_use` — Overture polygon query → classify → atomic PostGIS publish; never represented as official AGIS zoning. |

The `layer_registry` table (Alembic migration `0002`) is the shared source of truth
for current layer versions; the API reads it to stamp scorecards, ETL bumps it on
publish.

## POI data sources — beyond OSM (`aia_etl/sources/`)

AIA is **not limited to OpenStreetMap**. POIs are normalised from any open
provider into the shared `poi` schema, tagged with a `source` so provenance is
kept and each provider refreshes independently. Adding a provider is a new
adapter, not a schema or API change.

| Adapter | Source | License | Notes |
|---|---|---|---|
| `overpass` | OpenStreetMap (Overpass API) | ODbL | Comprehensive AOI coverage, no bulk download. |
| `overture` | Overture Maps Places | mixed upstream licenses; attribution required | Open, non-OSM aggregation queried via DuckDB over public GeoParquet. Release comes from Overture's live STAC catalog. |
| `grid3` | GRID3 Nigeria health facilities v2.0 + schools | Health: CC BY 4.0; schools: attribution required | Public ArcGIS FeatureServer layers; FCT endpoint check returned 1,107 health facilities and 2,060 schools on 2026-08-04. |

Configure with `POI_SOURCES` (comma-separated), `OVERTURE_RELEASE`, and the
GRID3 FeatureServer layer URLs in `.env`. All configured providers must return
valid AOI records before the transaction replaces any live rows or advances the
`poi` layer version.

```bash
# Refresh POIs for the FCT from the configured sources (default: overpass):
celery -A aia_etl.celery_app call aia_etl.tasks.amenities.refresh_amenities

# Or synchronously, choosing sources:
docker compose run --rm etl-worker python -c \
  "from aia_etl.tasks.amenities import refresh_amenities; print(refresh_amenities(sources=['overpass','overture']))"
```

Each successful run atomically replaces the requested providers, bumps the `poi`
layer version, and invalidates dependent cached scorecards. Records are
de-duplicated across providers (same-category points on a ~11 m grid, preferring
named entries) so overlapping providers merge cleanly. A provider failure leaves
the previous published dataset and registry version untouched.

## Google Earth Engine (DEM + remote sensing)

`aia_etl/gee.py` sources the DEM (and other imagery analysis) from Earth Engine
instead of manually downloaded tiles. Auth is service-account based, read from
the root `.env`:

- `GEE_SERVICE_ACCOUNT_EMAIL`
- `GEE_SERVICE_ACCOUNT_KEY` — path to the JSON key file **or** the JSON content itself
- `GEE_PROJECT` — optional; parsed from the SA email when unset

Exports:
- `export_dem_cop30(bbox, out)` — Copernicus GLO-30 DEM mosaic for the AOI.
- `export_s2_composite(bbox, out, start, end)` — cloud-masked Sentinel-2 median
  composite (RGB+NIR) for vegetation/NDVI analysis.

> `getDownloadURL` caps at a few tens of MB. For an AOI beyond that (all of FCT
> at 30 m), tile the bbox or switch to `ee.batch.Export.image.toCloudStorage`.

## Run

```bash
# Local dev via the root compose stack (adds etl-worker + etl-beat):
docker compose up --build etl-worker etl-beat

# Trigger a pipeline manually (inside the worker container or a shell with deps):
celery -A aia_etl.celery_app call aia_etl.tasks.osm.refresh_osm
celery -A aia_etl.celery_app call aia_etl.tasks.flood_tiles.mirror_hazard_tiles
celery -A aia_etl.celery_app call aia_etl.tasks.land_use.refresh_land_use

# DEM straight from Earth Engine (Copernicus GLO-30) → slope/flow-acc/TWI COGs:
celery -A aia_etl.celery_app call aia_etl.tasks.dem.dem_from_gee
```

## Tests

Pure-logic tests (versioning, staleness, categorisation, QA) run without the geo
stack or a database:

```bash
cd etl
pip install pytest "sqlalchemy>=2.0"
python -m pytest -q
```

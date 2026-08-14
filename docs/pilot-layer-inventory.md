# FCT pilot layer inventory

_Checklist for subdomain go-live. Query: `SELECT layer, version, source, notes FROM layer_registry ORDER BY layer`._

## Replace before pilot (demo-labelled)

| Layer | Version (pre-publish) | Source | Action |
|-------|----------------------|--------|--------|
| `roads` | `2026.07.demo` | `demo-seed` | **Replace** — `aia_etl.tasks.osm.refresh_osm` (Geofabrik → osm2pgsql) |
| `security` | `2026.07.demo` | `demo-seed` | **Republish** — `aia_etl.tasks.pilot_context.republish_security` (OSM police + area-council aggregates, ward-aware path) |
| `planning` | `2026.07.demo` | `demo-seed` | **Republish** — `aia_etl.tasks.pilot_context.republish_planning` (advisory overlays; AGIS licensed vectors deferred) |
| `poi` (residual) | — | `demo-seed` rows | **Remove** — `refresh_amenities` deletes `demo-seed` POIs on publish |

## OK for pilot (production or open-reference)

| Layer | Source | Notes |
|-------|--------|-------|
| `poi` | overpass / overture / grid3 | Multi-source amenity refresh |
| `dem` | Copernicus GLO-30 | Feasibility terrain |
| `land_use` | Overture / OSM | Open reference; not statutory AGIS zoning |
| `land_cover` | ESA WorldCover 2021 | Observed cover |
| `market` | Groundwork Data Abuja Housing v1 | QA-passed samples |
| `administrative_boundaries` | GRID3 NGA Operational Wards | 62 FCT wards |
| `buildings_3d` / `vegetation_3d` | Overture / ESA | Professional 3D context |
| `population` / `settlement` / `surface_heat` | GHSL / Landsat via GEE | Livability inputs |
| `flood` | GGIS Flood Watch (live) | Hazard mirror optional (`hazard` may stay `unpublished`) |

## Deferred (explicitly out of pilot gate)

| Item | Reason |
|------|--------|
| `hazard` COG mirror | Blocked until GGIS export coverage exists |
| `planning` AGIS vectors | Licensed dataset + web-reuse approval pending |
| Ward-level `incidents_agg` | Partner feed (e.g. ACLED) not wired; district fallback labelled in UI |
| OSRM travel times | Accessibility remains distance-based for pilot |

## Post-publish verification

```bash
curl -s http://localhost:8001/v1/meta/readiness | jq .
docker compose exec -T db psql -U aia -d propinsight -c \
  "SELECT layer, version, source FROM layer_registry WHERE source = 'demo-seed';"
python scripts/pilot_smoke_test.py http://localhost:8001
```

Expected: **zero** rows with `source = demo-seed` after Phase A completes.

## QA snapshot (2026-08-14)

| Check | Result |
|-------|--------|
| POI refresh (`2026.08.5`) | 6003 POIs — overpass 912, overture 1943, grid3 3148 |
| Demo POIs removed | ✅ no `demo-seed` rows in `poi` |
| Security republish (`2026.08.1`) | 25 incidents relabelled; 15 OSM police |
| Planning republish (`2026.08.1`) | 5 advisory overlays; AGIS deferred |
| OSM roads | ✅ `2026.08.1` — 84,648 Geofabrik/OSM centrelines published |

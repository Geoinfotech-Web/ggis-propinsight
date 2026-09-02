# GGIS PropInsight — AIA

**Accommodation Intelligence Application (AIA)** — the engineering codename for
**GGIS PropInsight**, a location-intelligence web platform for estate development,
home building, and property-acquisition decisions in Nigeria. FCT is the first
fully published state in a phased nationwide rollout.

> Public-facing branding is **GGIS PropInsight**; repositories, schemas, and internal
> artefacts use the **AIA** identifier. See `docs/` for the Project Overview (v1.2),
> Technical Design Document (v1.1), and Implementation Plan.

## Monorepo layout

```
apps/web/          React 18 + TS + Vite + MapLibre GL + Tailwind (PWA shell)
services/api/      FastAPI modular monolith (gateway + service modules)
  app/flood/                 GGIS Flood Watch client (+ graceful degradation)
  app/location_intelligence/ eight-domain scorecard orchestration
  app/scoring/               weighted multi-criteria engine (TDD §4.4)
  app/models.py              PostGIS schema v1 (TDD §6.1)
  migrations/                Alembic
services/mock-ggis/  Mock GGIS Flood Watch API — unblocks local dev
etl/               Geoprocessing pipelines (Celery/GDAL) — Phase 1
docs/              Overview, Technical Design, Implementation Plan
```

## Quick start (Docker)

```bash
cp .env.example .env      # then put the real GGIS Flood Watch key in .env
docker compose up --build
```

- API:        http://localhost:8001  (`/health`, `/docs`, `/v1/meta/flood`)
- Web:        http://localhost:5174
- Admin GIS:  http://localhost:5174/admin
- Mock GGIS:  http://localhost:9100/v1/meta/model

The API container runs `alembic upgrade head` on start (creates the PostGIS schema
and seeds the `fct-v1` scoring profile), then serves with autoreload.

### Admin GIS console

Set one of the admin bootstrap options in `.env`, then restart the API:

```bash
AIA_ADMIN_EMAIL=admin@example.com
AIA_ADMIN_PASSWORD=change-this
# or AIA_ADMIN_PASSWORD_HASH=<passlib pbkdf2_sha256 hash>
```

The `/admin` console accepts zipped shapefiles and GeoJSON for state, LGA,
ward, and masterplan uploads. Batches are validated and previewed before publish;
publishing bumps per-state layer readiness and rollback restores the previous
published batch when available.

### Try the core endpoint

```bash
curl -s http://localhost:8001/v1/locations/analyze \
  -H "Content-Type: application/json" \
  -d '{"geometry":{"type":"Point","coordinates":[7.3986,8.9634]}}'
```

Flood is **live** (via GGIS / mock). POIs can be refreshed from OSM Overpass,
Overture Maps, and GRID3 Nigeria. The map also serves a versioned open land-use
reference layer from Overture/OpenStreetMap (residential, industrial, commercial,
institutional, protected/reserve, agricultural, and related classes), clipped to
the current GRID3 operational FCT boundary. A separate 10 m ESA WorldCover COG
provides wall-to-wall observed cover across FCT. Both are context—not statutory
zoning; confirm allocations and development rights with AGIS/FCTA. A prepared
AGIS/FCTA vector importer gives licensed official plans precedence when acquired.

Investor and Developer reports also provide an on-demand professional 3D view.
Its default Analytical mode uses the full published FCT subset of Overture
building footprints and satellite-observed tree-canopy zones within the nearest
3 km. Google Photorealistic 3D Tiles can be selected as visual imagery context
when the configured Cesium ion account has coverage; it is never treated as an
analytical source or cached into PropInsight data layers.

Every fresh web session opens a guided welcome journey: product introduction,
a plain-language goal question, address/coordinate selection, draggable map-pin
confirmation, persona, radius, and analysis. The goal answer marks a suggested
persona without preventing the user from choosing another. Direct map clicks no
longer start an analysis.
The committed Scorecard keeps its main actions compact: **Edit analysis** opens
the audience/radius controls, and professional personas receive a separate
icon-labelled **3D site view** button. A PDF export button appears in the header
as **Download report** only after the user selects **View on map**. Before a report is committed, the
map legend shows only the FCT land-use reference; report-specific score,
amenity, security, land-cover, project, and buffer entries appear afterwards.

Security resolves each point to its GRID3 ward and uses local police proximity.
Ward incident aggregates are used only when a source actually publishes them;
otherwise the report clearly labels the broader district fallback rather than
presenting district totals as neighbourhood crime data.

Livability and professional development context are published to local,
versioned data from Earth Engine. The environmental refresh combines Dynamic
World cover with a cloud-masked median of the three most recent complete Landsat
dry seasons. GHSL supplies the 2025 population estimate, 2030 projection, and
built-surface change. Feasibility uses a fixed 1 km profile built from 100 m
Copernicus GLO-30 terrain samples. Investor
and Developer reports also include official FCTA, NOCOPO, and Budget Office
project records; Tenant and Home Buyer reports do not expose that professional
outlook.

After configuring the Earth Engine service account and any structured official
project feeds in `.env`, run:

```bash
docker compose exec etl-worker celery -A aia_etl.celery_app call \
  aia_etl.tasks.environment.refresh_environmental_metrics
docker compose exec etl-worker celery -A aia_etl.celery_app call \
  aia_etl.tasks.projects.refresh_development_projects
```

The environmental task defaults to `ENVIRONMENT_SOURCE=gee`; the legacy direct
download path remains available as an explicit fallback. Project ingestion rejects non-official hosts,
undated records, and unrecognised lifecycle stages. Scheduled refreshes run
annually for environmental metrics and weekly for verified projects when
`etl-beat` is running.

```bash
# Open land-use GeoJSON for the current map viewport
curl -s "http://localhost:8001/v1/locations/land-use?min_lon=7.30&min_lat=8.90&max_lon=7.65&max_lat=9.20"

# Observed-cover metadata and raster tiles
curl -s http://localhost:8001/v1/locations/land-cover/meta
curl -o cover.png http://localhost:8001/v1/locations/land-cover/tiles/10/533/486.png
```

## Frontend dev

```bash
cd apps/web
npm install
npm run dev        # http://localhost:5174 — proxies /v1 to the API
```

## Tests

```bash
cd services/api
pip install -e ".[dev]"
pytest -q

cd ../../etl
python -m pytest -q
```

## GGIS Flood Watch integration

Set `GGIS_FLOOD_DATA_MODE=live` with
`GGIS_FLOOD_BASE_URL=https://api.gfw.ggis.africa`. The deployed Developer API
authenticates with `X-API-Key` and exposes point susceptibility plus intersecting
and nearby flood zones through `/v1/location/site-assessment`.

GGIS currently publishes a susceptibility class rather than a numerical point
hazard score. PropInsight therefore reports a transparent ordinal hazard index:
Very Low = 10, Low = 25, Moderate = 50, High = 75, and Very High or Highly
Susceptible = 90. The index is higher-is-worse and its inverse is used as the
flood suitability contribution to fit and feasibility. It is decision-support
classification—not flood probability, a surveyed level, or a replacement for
site drainage investigation. The public report keeps this explanation concise;
the mapping is documented here for auditability.

Local mock values remain demo evidence and are excluded from fit, highlights,
and feasibility. If the live service is unreachable, flood degrades to
timestamped last-known evidence (or temporarily unavailable) while the rest of
the scorecard still returns.

## Status

Phase 1 data activation: the application scaffold and scorecard are operational;
the current focus is replacing demo-backed layers with QA-gated production data.

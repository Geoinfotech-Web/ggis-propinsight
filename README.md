# GGIS PropInsight — AIA

**Accommodation Intelligence Application (AIA)** — the engineering codename for
**GGIS PropInsight**, a location-intelligence web platform for estate development,
home building, and property-acquisition decisions in Nigeria. Pilot: FCT (Abuja).

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
- Mock GGIS:  http://localhost:9100/v1/meta/model

The API container runs `alembic upgrade head` on start (creates the PostGIS schema
and seeds the `fct-v1` scoring profile), then serves with autoreload.

### Try the core endpoint

```bash
curl -s http://localhost:8001/v1/locations/analyze \
  -H "Content-Type: application/json" \
  -d '{"geometry":{"type":"Point","coordinates":[7.3986,8.9634]}}'
```

Flood is **live** (via GGIS / mock). POIs can be refreshed from OSM Overpass,
Overture Maps, and GRID3 Nigeria. Roads, DEM, security, and planning remain
demo-backed until their production ETL layers pass QA and publish atomically.

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

AIA never re-derives flood risk locally (TDD §5.3). The flood domain is served live
from GGIS Flood Watch; if GGIS is unreachable the domain **degrades gracefully** to a
timestamped last-known class (or "temporarily unavailable") and the rest of the
scorecard still returns. Set `GGIS_FLOOD_*` in `.env`.

## Status

Phase 1 data activation: the application scaffold and scorecard are operational;
the current focus is replacing demo-backed layers with QA-gated production data.

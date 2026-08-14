# GGIS PropInsight (AIA) — Handoff

_Last updated: 2026-08-13_

Engineering handoff for **GGIS PropInsight** (internal codename **AIA**), a location
intelligence web platform for the Nigerian property market. Pilot: **FCT / Abuja**.
Repo: <https://github.com/Geoinfotech-Web/ggis-propinsight>. See `docs/` for the
Project Overview (v1.2), Technical Design Document (v1.1), and Implementation Plan.

---

## 1. Current status (Phase 1 — Foundation)

| Area | State |
|---|---|
| Monorepo scaffold (api / etl / web / infra) | ✅ done |
| GGIS Flood Watch client + graceful degradation (TDD §5.3) | ✅ live Developer API adapter + mock fallback |
| PostGIS schema v1 (TDD §6.1) + Alembic (0001–0016) | ✅ done |
| Scoring engine (weighted multi-criteria, TDD §4.4) | ✅ done |
| `analyze` path: layer_registry stamping + Redis cache (TDD §2.2, §10) | ✅ done |
| ETL package: `layer_version` discipline, OSM/DEM/flood tasks | ✅ done |
| Google Earth Engine environmental source | ✅ authenticated and published locally |
| React + MapLibre guided analysis + PDF export | ✅ runs locally |
| CI (api + etl + web) | ✅ done |
| Multi-source POIs (Overpass + Overture + GRID3) | ✅ adapters configured; transactional publish + QA gates added |
| Amenity / accessibility / feasibility domains | ✅ OSM roads + multi-source POIs published for pilot |
| FCT land context | ✅ GRID3-clipped Overture uses + full-FCT ESA WorldCover 10 m observed cover published |
| Official AGIS/FCTA planning import | ✅ importer ready; ⚠️ licensed vector dataset and web-reuse permission still required |

Flood, amenities, market, Habitability, terrain feasibility, land context, and
professional development context are active locally. **Pilot publish complete:**
multi-source POIs (6k+), OSM roads (84k segments), security/planning republished
off `demo-seed`. See `docs/pilot-layer-inventory.md` and `docs/deploy-brief.md`
for subdomain handover.

---

## 2. What's running locally right now

Containers are **up** so the app can be explored (project name `aia`):

| Service | Container | URL / port |
|---|---|---|
| API (FastAPI) | `aia-api-1` | http://localhost:8001 (`/health`, `/docs`, `/v1/...`) |
| PostGIS 16 | `aia-db-1` | localhost:5432 |
| Redis | `aia-redis-1` | localhost:6379 |
| Mock GGIS Flood Watch | `aia-mock-ggis-1` | http://localhost:9100/v1/meta/model |
| Web dev server (Vite) | `aia-web-1` | http://localhost:5174 |

> **Port note:** the real **GGIS Flood Watch stack** (`flood_*` containers) runs on
> the same host and holds **8000** and **5173**. AIA therefore uses **8001** for the
> API and **5174** for the web dev server. This is baked into
> `docker-compose.yml` and `apps/web/vite.config.ts` (proxy → 8001).

### Explore it
- Open the web app and search, geolocate, or click the map → choose a persona and
  radius → analyse → select **View on map**.
- API docs / try endpoints: http://localhost:8001/docs
- Prove the GGIS integration: `curl http://localhost:8001/v1/meta/flood`
- Sample analyze call:
  ```bash
  curl -s http://localhost:8001/v1/locations/analyze \
    -H "Content-Type: application/json" \
    -d '{"geometry":{"type":"Point","coordinates":[7.3986,8.9634]}}'
  ```

---

## 3. Running things from scratch

```bash
# 1. Core stack (db, redis, mock-ggis, API, web)
docker compose up -d db redis mock-ggis api web  # API runs `alembic upgrade head` on start

# 2. ETL worker / beat (optional; needed for scheduled/queued pipelines)
docker compose up -d etl-worker etl-beat
```

- `docker compose ps` — see AIA services and health.
- `docker compose logs -f api` — API logs.
- `docker compose down` — stop AIA services (add `-v` to also drop the pgdata/geodata volumes).

### Tests
```bash
cd services/api && pip install -e ".[dev]" && pytest -q      # 99 tests
cd etl && pip install -e ".[dev]" && pytest -q               # 70 tests
```

---

## 4. Secrets & local config (IMPORTANT)

- `.env` (gitignored) holds the real secrets: GGIS Flood Watch key/HMAC, JWT secret,
  and GEE service-account details. Never commit it. `.env.example` documents every var.
- The Earth Engine service-account credential is supplied through the configured
  local secret path or JSON environment value. It must remain outside version
  control; never record its filename or contents in public documentation.
- **`docker-compose.override.yml`** (gitignored, local only) mounts that key into the
  ETL containers at `/secrets/gee-key.json` so Earth Engine can authenticate.

---

## 5. Google Earth Engine status

Earth Engine IAM is configured. The current environment task publishes terrain,
land-cover/heat context, population and settlement evidence to local versioned
layers. To refresh:
```bash
docker compose run --rm etl-worker python -c \
  "from aia_etl.tasks.dem import dem_from_gee; print(dem_from_gee(bbox=[7.44,9.03,7.54,9.10], scale=30))"
```
Keep direct `getDownloadURL` requests spatially bounded; use tiled exports for
full-FCT refreshes.

---

## 6. Architecture quick reference

- **Modular monolith** API (TDD §1.4): `app/` sub-packages = flood, location_intelligence,
  scoring, (accessibility/reports/community/ai_assistant to come), gateway in `main.py`.
- **`layer_version` discipline** is the cache-correctness backbone: `layer_registry`
  is the shared source of truth; ETL `bump_layer` publishes a new version and
  `sweep_stale_scores` invalidates dependent DB scores. The Redis cache key includes
  the layer versions, so a bump changes the key and the next request recomputes.
- **Flood evidence stays anchored to GGIS Flood Watch.** The current Developer
  API returns a class, not a point score, so PropInsight converts that class to
  an audited ordinal hazard index: Very Low 10, Low 25, Moderate 50, High 75,
  Very High/Highly Susceptible 90. Never describe it as probability or a
  GGIS-published numerical score.

Key files:
- `services/api/app/flood/client.py` — GGIS client + graceful degradation.
- `services/api/app/location_intelligence/service.py` — scorecard fan-out + cache.
- `services/api/app/models.py` — PostGIS schema v1.
- `etl/aia_etl/layers.py` — versioning + cache-invalidation sweep.
- `etl/aia_etl/gee.py` — Earth Engine DEM / Sentinel-2 exports.
- `etl/aia_etl/tasks/` — osm, dem, flood_tiles pipelines.
- `etl/aia_etl/tasks/land_use.py` — Overture/OSM open land-use context publisher.
- `etl/aia_etl/tasks/boundaries.py` — GRID3 FCT ward dissolve / clipping boundary.
- `services/api/app/location_intelligence/security.py` — ward-aware security with an explicit district incident fallback.
- `etl/aia_etl/tasks/land_cover.py` — Dynamic World preferred, ESA WorldCover fallback COG.
- `etl/aia_etl/tasks/official_land_use.py` — licensed AGIS/FCTA vector importer.
- `services/api/app/location_intelligence/land_use.py` — viewport GeoJSON and point classification; AGIS advisory boundary.
- `services/api/app/location_intelligence/land_cover.py` — observed-cover point sampling, metadata, and PNG tiles.
- `services/api/app/location_intelligence/professional_3d.py` — bounded Overture building and canopy evidence endpoints.
- `apps/web/src/components/ScorecardConsole.tsx` — compact Edit analysis / 3D site-view actions and domain cards.

---

## 7. Recommended next steps

1. **Stage and run the atomic multi-source POI refresh** for Overpass, Overture,
   and GRID3; review coverage, duplicates, attribution, and category counts before publish.
2. **Run the canonical OSM roads publish** from a current Geofabrik extract, then
   replace straight-line accessibility proxies with OSRM/Valhalla travel times.
3. **Replace remaining demo-labelled road, security, and planning layers** with
   QA-gated production publications.
4. **Implement the GGIS hazard coverage export** before enabling hazard mirroring;
   the current task intentionally reports `blocked` rather than publishing an empty COG.
5. **Persist scorecards to the `scores` table** (not just Redis) so the ETL
   `sweep_stale_scores` has durable rows to invalidate.
6. **Check domain readiness** — `GET /v1/meta/readiness` (and
   `etl/aia_etl/domain_deps.py`) for the Phase 1 unlock matrix.
7. **Branch protection** on `main` + require CI, then move to PR-based flow.
8. **Acquire the official AGIS land-use/masterplan vectors and reuse approval**;
   run `aia_etl.tasks.official_land_use.import_official_land_use`. The API/UI
   already give `official_masterplan` precedence over Overture/OSM reference use.
9. **Review Dynamic World freshness** periodically; ESA WorldCover remains the
   explicit fallback when a current GEE composite cannot pass publication QA.

---

## 8. Git

- Branch: `main`, pushed to `origin`.
- Recent commits: scaffold → ETL package → analyze cache + GEE → local-run fixes.
- Commit author is set to `Geoinfotech <ebenzblog9@gmail.com>` locally; adjust if a
  different GitHub identity is preferred.

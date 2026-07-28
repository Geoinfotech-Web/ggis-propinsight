# GGIS PropInsight (AIA) — Handoff

_Last updated: 2026-07-28_

Engineering handoff for **GGIS PropInsight** (internal codename **AIA**), a location
intelligence web platform for the Nigerian property market. Pilot: **FCT / Abuja**.
Repo: <https://github.com/Geoinfotech-Web/ggis-propinsight>. See `docs/` for the
Project Overview (v1.2), Technical Design Document (v1.1), and Implementation Plan.

---

## 1. Current status (Phase 1 — Foundation)

| Area | State |
|---|---|
| Monorepo scaffold (api / etl / web / infra) | ✅ done |
| GGIS Flood Watch client + graceful degradation (TDD §5.3) | ✅ done, live via mock |
| PostGIS schema v1 (TDD §6.1) + Alembic (0001, 0002) | ✅ done |
| Scoring engine (weighted multi-criteria, TDD §4.4) | ✅ done |
| `analyze` path: layer_registry stamping + Redis cache (TDD §2.2, §10) | ✅ done |
| ETL package: `layer_version` discipline, OSM/DEM/flood tasks | ✅ done |
| Google Earth Engine DEM source | ⚠️ code done; **blocked on GCP IAM** (see §5) |
| React + MapLibre web shell (click-to-analyse) | ✅ runs locally |
| CI (api + etl + web) | ✅ done |
| Amenity / accessibility / feasibility domains | ⚠️ scoring wired; FCT demo seed (`0003`) publishes poi/roads/dem for local analyse |

**Flood** is the only domain returning a live score; the other Tier-1 domains
(`amenities`, `accessibility`, `feasibility`) return `status: "pending"` until
their ETL layers publish. Tier 2–3 domains (`security`, `tenure`, `market`,
`livability`) are later phases. No domain is ever surfaced with a fabricated score.

---

## 2. What's running locally right now

Containers are **up** so the app can be explored (project name `aia`):

| Service | Container | URL / port |
|---|---|---|
| API (FastAPI) | `aia-api-1` | http://localhost:8001 (`/health`, `/docs`, `/v1/...`) |
| PostGIS 16 | `aia-db-1` | localhost:5432 |
| Redis | `aia-redis-1` | localhost:6379 |
| Mock GGIS Flood Watch | `aia-mock-ggis-1` | http://localhost:9100/v1/meta/model |
| Web dev server (Vite) | (host process) | http://localhost:52591 _(ephemeral; see §3)_ |

> **Port note:** the real **GGIS Flood Watch stack** (`flood_*` containers) runs on
> the same host and holds **8000** and **5173**. AIA therefore uses **8001** for the
> API and an auto-assigned port for the web dev server. This is baked into
> `docker-compose.yml` (api `8001:8000`) and `apps/web/vite.config.ts` (proxy → 8001).

### Explore it
- Open the web app and **click any point on the map** → live scorecard.
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
# 1. Backend stack (db, redis, mock-ggis, api on 8001)
docker compose up -d db redis mock-ggis api      # api runs `alembic upgrade head` on start

# 2. Web dev server (Vite auto-picks a free port; prints the URL)
cd apps/web && npm install && npm run dev

# 3. ETL worker / beat (optional; needed for scheduled/queued pipelines)
docker compose up -d etl-worker etl-beat
```

- `docker compose ps` — see AIA services and health.
- `docker compose logs -f api` — API logs.
- `docker compose down` — stop AIA services (add `-v` to also drop the pgdata/geodata volumes).

### Tests
```bash
cd services/api && pip install -e ".[dev]" && pytest -q      # 6 tests
cd etl && pip install pytest "sqlalchemy>=2.0" pydantic-settings requests && pytest -q   # 18 tests
```

---

## 4. Secrets & local config (IMPORTANT)

- `.env` (gitignored) holds the real secrets: GGIS Flood Watch key/HMAC, JWT secret,
  and GEE service-account details. Never commit it. `.env.example` documents every var.
- **`ggis-flood-watch-<hash>.json`** — the GCP service-account key file sits in the
  repo root. It is **gitignored** and confirmed absent from git history. Consider
  moving it out of the repo (e.g. `~/.config/gee/`) and updating
  `GEE_SERVICE_ACCOUNT_KEY` to the new path.
- **`docker-compose.override.yml`** (gitignored, local only) mounts that key into the
  ETL containers at `/secrets/gee-key.json` so Earth Engine can authenticate.

---

## 5. Known blocker: Google Earth Engine IAM

The DEM-from-GEE task authenticates successfully but fails with:

> `Caller does not have required permission to use project ggis-flood-watch.
> Grant the caller the roles/serviceusage.serviceUsageConsumer role...`

**To unblock (Google Cloud console, project `ggis-flood-watch`):**
1. Grant the service account the **Service Usage Consumer**
   (`roles/serviceusage.serviceUsageConsumer`) role.
2. **Enable the Earth Engine API** on the project.
3. Ensure the project is **registered for Earth Engine** (code.earthengine.google.com).

If Earth Engine lives under a different Cloud project, set `GEE_PROJECT=<that-project>`
in `.env` instead (the code otherwise parses the project from the SA email).

**Then run:**
```bash
docker compose run --rm etl-worker python -c \
  "from aia_etl.tasks.dem import dem_from_gee; print(dem_from_gee(bbox=[7.44,9.03,7.54,9.10], scale=30))"
```
Produces `slope.tif`, `flow_accumulation.tif`, `twi.tif` COGs (in the `geodata`
volume) and bumps the `dem` layer. Keep the AOI small — `getDownloadURL` caps at a
few tens of MB; tile the bbox or use `Export.image.toCloudStorage` for all of FCT.

---

## 6. Architecture quick reference

- **Modular monolith** API (TDD §1.4): `app/` sub-packages = flood, location_intelligence,
  scoring, (accessibility/reports/community/ai_assistant to come), gateway in `main.py`.
- **`layer_version` discipline** is the cache-correctness backbone: `layer_registry`
  is the shared source of truth; ETL `bump_layer` publishes a new version and
  `sweep_stale_scores` invalidates dependent DB scores. The Redis cache key includes
  the layer versions, so a bump changes the key and the next request recomputes.
- **Flood science stays in GGIS Flood Watch** — AIA never re-derives flood risk.

Key files:
- `services/api/app/flood/client.py` — GGIS client + graceful degradation.
- `services/api/app/location_intelligence/service.py` — scorecard fan-out + cache.
- `services/api/app/models.py` — PostGIS schema v1.
- `etl/aia_etl/layers.py` — versioning + cache-invalidation sweep.
- `etl/aia_etl/gee.py` — Earth Engine DEM / Sentinel-2 exports.
- `etl/aia_etl/tasks/` — osm, dem, flood_tiles pipelines.

---

## 7. Recommended next steps

1. **Unblock GEE IAM** (§5) and run `dem_from_gee` to produce the first real
   slope/flow-accumulation/TWI COGs for FCT.
2. **OSM roads & POIs ETL** — run `refresh_osm` (needs a Geofabrik extract) to
   populate `poi`/`roads`, flipping `amenities` from `pending` to live (scoring
   is already wired). Then finish accessibility via OSRM/Valhalla travel times.
3. **Serve DEM/hazard tiles** via TiTiler + `martin`, and register a `layer switcher`
   in the web app.
4. **Persist scorecards to the `scores` table** (not just Redis) so the ETL
   `sweep_stale_scores` has durable rows to invalidate.
5. **Check domain readiness** — `GET /v1/meta/readiness` (and
   `etl/aia_etl/domain_deps.py`) for the Phase 1 unlock matrix.
6. **Branch protection** on `main` + require CI, then move to PR-based flow.

---

## 8. Git

- Branch: `main`, pushed to `origin`.
- Recent commits: scaffold → ETL package → analyze cache + GEE → local-run fixes.
- Commit author is set to `Geoinfotech <ebenzblog9@gmail.com>` locally; adjust if a
  different GitHub identity is preferred.

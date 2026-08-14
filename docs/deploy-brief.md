# PropInsight — staging / production deploy brief (GCP, Flood Watch–aligned)

Hand this to the web team for subdomain cutover. Assumed URLs:

- Staging: `https://propinsight-staging.ggis.africa`
- Production: `https://propinsight.ggis.africa`

## Topology (minimal staging)

Mirror the existing Flood Watch GCP pattern: container services behind a load balancer with managed TLS and DNS under `ggis.africa`.

| Service | Image / artifact | Notes |
|---------|------------------|-------|
| PostGIS 16 | `postgis/postgis:16-3.4` | Persistent volume; run `alembic upgrade head` on API start |
| Redis 7 | `redis:7-alpine` | Cache + Celery broker |
| API | `services/api` Dockerfile | FastAPI on `:8000` internal |
| Web | `apps/web/Dockerfile.prod` | nginx serves SPA; proxies `/v1` and `/health` to API |
| ETL worker/beat | `etl` Dockerfile | Optional on staging unless scheduled refreshes needed |
| mock-ggis | **Off** in staging/prod | Use live GGIS Flood Watch |

Build production web from repo root:

```bash
docker build -f apps/web/Dockerfile.prod -t ggis/propinsight-web:pilot .
```

## Reverse proxy paths

| Path | Target |
|------|--------|
| `/` | SPA static (`index.html` fallback) |
| `/v1/*` | API gateway |
| `/health` | API liveness |

Health check: `GET /health` → `{"status":"ok",...}`

## Staging environment matrix

Copy from [`.env.example`](../.env.example). Minimum staging values:

| Variable | Staging value |
|----------|---------------|
| `AIA_ENV` | `staging` |
| `CORS_ORIGINS` | `https://propinsight-staging.ggis.africa` |
| `GGIS_FLOOD_DATA_MODE` | `live` |
| `GGIS_FLOOD_BASE_URL` | Production Flood Watch API base (same GCP project) |
| `GGIS_FLOOD_API_KEY` | Service key (Secret Manager) |
| `GGIS_FLOOD_HMAC_SECRET` | HMAC secret (Secret Manager) |
| `POSTGRES_*` | Cloud SQL or managed PostGIS credentials |
| `REDIS_URL` | Managed Redis URL |
| `JWT_SECRET` | Random 32+ byte secret |
| `POI_SOURCES` | `overpass,overture,grid3` |
| `GEE_SERVICE_ACCOUNT_*` | Only if ETL GEE tasks run in staging; else omit |

### Vite build args (web image)

| Build arg | Required | Notes |
|-----------|----------|-------|
| `VITE_CESIUM_ION_TOKEN` | Optional | Photorealistic 3D; analytical mode works without it |
| `VITE_3D_TERRAIN_ENABLED` | Optional | Default `false` |
| `VITE_TERRAIN_TILEJSON_URL` | Optional | MapTiler / MapTernhorn tilejson |
| `VITE_BUILDINGS_TILEJSON_URL` | Optional | OpenFreeMap default |

## GCP checklist

- [ ] DNS `A`/`AAAA` or `CNAME` for staging subdomain → load balancer
- [ ] Managed TLS certificate for staging hostname
- [ ] Secret Manager entries for DB, Redis, JWT, GGIS keys (GEE key only if ETL runs)
- [ ] Firewall: public 443 only; PostGIS/Redis internal
- [ ] No Vite dev port (`5174`) exposed publicly

## Repo / CI

- Branch protection on `main` — require [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) (api + etl + web build)
- Tag pilot release after green CI: `git tag pilot-staging-1 && git push origin pilot-staging-1`

## Smoke test (Phase B / D)

After deploy:

```bash
python scripts/pilot_smoke_test.py https://propinsight-staging.ggis.africa
```

Manual UI checks:

1. Each persona: search → radius → analyse → View on map → domain list matches exclusions
2. Investor/Developer: 3D site view (analytical mode without Cesium token)
3. Flood ordinal disclaimer and land-use “not zoning” copy visible

## Staging sign-off → production

1. PropInsight team runs smoke on staging URL
2. Fix CORS / proxy / env with web team
3. Production subdomain only after staging sign-off
4. Soft-launch as **FCT pilot / advisory** — not statutory AGIS decision tool

## Branch protection (GitHub)

Settings → Branches → Add rule for `main`:

- Require pull request before merging
- Require status checks: `API — lint, type-check, tests`, `ETL — lint & pure-logic tests`, `Web — type-check & build`

Document-only; enable in GitHub UI by repo admin.

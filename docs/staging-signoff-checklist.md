# Staging sign-off checklist (Phase D)

Web team: complete items 1–6. PropInsight team: complete items 7–10 after staging URL is live.

## Web team

- [ ] Staging DNS `propinsight-staging.ggis.africa` resolves to load balancer
- [ ] TLS certificate active (managed cert on GCP LB)
- [ ] PostGIS + Redis + API + `web-prod` (nginx) running on Flood Watch GCP project
- [ ] `mock-ggis` **not** deployed; `GGIS_FLOOD_DATA_MODE=live`
- [ ] Secrets loaded from Secret Manager (see [`.env.staging.example`](../.env.staging.example))
- [ ] Reverse proxy: `/` → SPA, `/v1` → API, `/health` → API

## PropInsight team (post-deploy)

- [ ] `curl https://propinsight-staging.ggis.africa/health` → `status: ok`
- [ ] `python scripts/pilot_smoke_test.py https://propinsight-staging.ggis.africa`
- [ ] Manual UI smoke: four personas, 3D analytical view, flood disclaimer, land-use advisory copy
- [ ] CORS verified from staging origin (browser analyse call succeeds)

## Production cutover (after staging sign-off)

- [ ] Duplicate stack for `propinsight.ggis.africa`
- [ ] Update `CORS_ORIGINS` to production hostname
- [ ] Re-run smoke on production URL
- [ ] Soft-launch banner: **FCT pilot / advisory — not statutory AGIS zoning or title search**

## Rollback

- Keep previous container revision / image tag (`pilot-staging-1`) for quick revert
- DB migrations are forward-only; restore from snapshot if schema rollback needed

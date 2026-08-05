"""Scorecard cache (Redis) — the primary latency lever (TDD §10, §2.2).

Cached by geohash8 + layer_versions + scoring profile. Because the layer
versions are baked into the key, an ETL layer bump changes the key and new
requests naturally recompute — the cache is self-invalidating on publish, while
the durable `scores` table is swept separately by the ETL.

The cache is best-effort: any Redis error degrades to a cache miss rather than
failing the scorecard (consistent with the graceful-degradation philosophy).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

# Orphaned keys (from superseded layer versions) expire on their own.
DEFAULT_TTL_SECONDS = 24 * 3600
# Bump when the response composition or persona domain set changes so cached
# scorecards cannot preserve an older report experience for up to 24 hours.
REPORT_SCHEMA_VERSION = "v4"


class ScorecardCache:
    def __init__(self, client: aioredis.Redis, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        self._redis = client
        self._ttl = ttl

    @staticmethod
    def make_key(profile: str, geohash8: str, layer_versions: dict[str, str]) -> str:
        canon = json.dumps(layer_versions, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha1(canon.encode()).hexdigest()[:12]  # noqa: S324 (cache key, not security)
        return f"aia:scorecard:{REPORT_SCHEMA_VERSION}:{profile}:{geohash8}:{digest}"

    async def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self._redis.get(key)
        except Exception as exc:  # noqa: BLE001 — never fail the request on cache error
            log.warning("cache get failed (%s); treating as miss", exc)
            return None
        return json.loads(raw) if raw else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        try:
            await self._redis.set(key, json.dumps(value), ex=self._ttl)
        except Exception as exc:  # noqa: BLE001
            log.warning("cache set failed (%s); continuing", exc)


_client: aioredis.Redis | None = None


def get_cache() -> ScorecardCache:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return ScorecardCache(_client)

"""Read current published layer versions from `layer_registry` (TDD §4.3).

The API stamps every scorecard with the versions in force at computation time,
so cached results are traceable and self-invalidating (the versions are part of
the cache key). Unpublished layers are omitted.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

UNPUBLISHED = "unpublished"


async def current_layer_versions(session: AsyncSession) -> dict[str, str]:
    """Map of layer -> current version, excluding layers not yet published."""
    result = await session.execute(
        text("SELECT layer, version FROM layer_registry WHERE version <> :u"),
        {"u": UNPUBLISHED},
    )
    return {row.layer: row.version for row in result}

"""The `layer_version` discipline (TDD §4.3, §6.1) — the backbone of cache correctness.

Every published layer bump changes its version in `layer_registry`; dependent
cached `scores` (whose `layer_versions` JSONB references an older version) are
then invalidated. Pure helpers here are unit-tested without a database; the
DB-touching functions take a SQLAlchemy Connection so callers control the txn.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Canonical layer names tracked in the registry.
LAYERS = ("poi", "roads", "dem", "hazard", "planning", "market", "security")
UNPUBLISHED = "unpublished"


def next_calver(previous: str | None, now: datetime | None = None) -> str:
    """CalVer `YYYY.MM.N`: monthly, with an incrementing suffix within the month.

    >>> next_calver(None, datetime(2026, 7, 1))
    '2026.07.1'
    >>> next_calver('2026.07.1', datetime(2026, 7, 15))
    '2026.07.2'
    >>> next_calver('2026.06.3', datetime(2026, 7, 1))
    '2026.07.1'
    """
    now = now or datetime.now(UTC)
    stamp = f"{now.year}.{now.month:02d}"
    if previous and previous.startswith(stamp + "."):
        try:
            seq = int(previous.rsplit(".", 1)[1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{stamp}.{seq}"


def is_stale(score_layer_versions: dict[str, str], layer: str, current: str) -> bool:
    """True if a cached score depends on `layer` at a version other than `current`.

    A score that never referenced the layer is not made stale by that layer.
    """
    if layer not in score_layer_versions:
        return False
    return score_layer_versions[layer] != current


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------
def get_version(conn: Connection, layer: str) -> str | None:
    row = conn.execute(
        text("SELECT version FROM layer_registry WHERE layer = :layer"), {"layer": layer}
    ).first()
    return row[0] if row else None


def next_layer_version(conn: Connection, layer: str) -> str:
    """Return the next version without publishing it.

    ETL publishers use this to stamp staged rows, then update ``layer_registry``
    only after every data write has succeeded in the same database transaction.
    """
    if layer not in LAYERS:
        raise ValueError(f"unknown layer {layer!r}; expected one of {LAYERS}")
    previous = get_version(conn, layer)
    prev_for_calver = None if previous in (None, UNPUBLISHED) else previous
    return next_calver(prev_for_calver)


def set_version(
    conn: Connection, layer: str, version: str, source: str | None = None, notes: str | None = None
) -> None:
    """Upsert a layer's current published version."""
    conn.execute(
        text(
            """
            INSERT INTO layer_registry (layer, version, source, notes, updated_at)
            VALUES (:layer, :version, :source, :notes, :ts)
            ON CONFLICT (layer) DO UPDATE
              SET version = EXCLUDED.version,
                  source = COALESCE(EXCLUDED.source, layer_registry.source),
                  notes = EXCLUDED.notes,
                  updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "layer": layer,
            "version": version,
            "source": source,
            "notes": notes,
            "ts": datetime.now(UTC),
        },
    )


def sweep_stale_scores(conn: Connection, layer: str, current: str) -> int:
    """Invalidate cached scores that reference `layer` at any version but `current`.

    Returns the number of rows removed. Uses the JSONB `?` containment + `->>`
    extraction so only scores that actually depend on the layer are touched.
    """
    result = conn.execute(
        text(
            """
            DELETE FROM scores
            WHERE layer_versions ? :layer
              AND layer_versions ->> :layer IS DISTINCT FROM :current
            """
        ),
        {"layer": layer, "current": current},
    )
    return result.rowcount or 0


def bump_layer(
    conn: Connection, layer: str, source: str | None = None, notes: str | None = None
) -> tuple[str, int]:
    """Publish a new version for `layer` and invalidate dependent scorecards.

    Returns (new_version, invalidated_score_count).
    """
    new_version = next_layer_version(conn, layer)
    set_version(conn, layer, new_version, source=source, notes=notes)
    invalidated = sweep_stale_scores(conn, layer, new_version)
    return new_version, invalidated

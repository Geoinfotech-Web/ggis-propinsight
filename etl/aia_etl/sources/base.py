"""Source-agnostic POI record + ingestion primitives."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from aia_etl.poi_categories import AIA_CATEGORIES

# Approximate FCT (Abuja) bbox (min_lon, min_lat, max_lon, max_lat).
FCT_BBOX: tuple[float, float, float, float] = (6.75, 8.25, 7.75, 9.35)


@dataclass(frozen=True)
class PoiRecord:
    lon: float
    lat: float
    category: str          # one of AIA_CATEGORIES
    name: str | None
    source: str            # provenance, e.g. "overpass", "overture", "grid3"

    def valid(self, bbox: tuple[float, float, float, float] | None = None) -> bool:
        if self.category not in AIA_CATEGORIES:
            return False
        if not (-180 <= self.lon <= 180 and -90 <= self.lat <= 90):
            return False
        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            if not (min_lon <= self.lon <= max_lon and min_lat <= self.lat <= max_lat):
                return False
        return True


def _cell(lon: float, lat: float, precision: int = 4) -> tuple[float, float]:
    return (round(lon, precision), round(lat, precision))


def dedup_records(records: list[PoiRecord], precision: int = 4) -> list[PoiRecord]:
    """Drop near-duplicate POIs of the same category (~11 m grid at precision 4).

    Keeps the first occurrence, preferring a named record when one collides with
    an unnamed one. Enables merging overlapping providers without double-counting.
    """
    best: dict[tuple[str, float, float], PoiRecord] = {}
    for rec in records:
        key = (rec.category, *_cell(rec.lon, rec.lat, precision))
        existing = best.get(key)
        if existing is None or (not existing.name and rec.name):
            best[key] = rec
    return list(best.values())


def replace_source_pois(
    conn: Connection,
    source: str,
    records: list[PoiRecord],
    layer_version: str,
) -> int:
    """Replace all POIs for one source with `records`. Returns rows written.

    Per-source replacement means providers refresh independently and one
    provider going stale never wipes another's data.
    """
    conn.execute(text("DELETE FROM poi WHERE source = :source"), {"source": source})
    if not records:
        return 0
    conn.execute(
        text(
            """
            INSERT INTO poi (geom, category, name, source, verified, layer_version)
            VALUES (
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
              :category, :name, :source, false, :ver
            )
            """
        ),
        [
            {
                "lon": r.lon,
                "lat": r.lat,
                "category": r.category,
                "name": r.name,
                "source": r.source,
                "ver": layer_version,
            }
            for r in records
        ],
    )
    return len(records)

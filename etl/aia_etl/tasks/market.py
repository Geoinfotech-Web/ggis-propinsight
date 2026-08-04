"""Tier-3 partner market sample ingestion (Overview section 4).

The monthly consolidated CSV is expected at ``DATA_DIR/market/market_samples.csv``.
Required columns: lon, lat, kind, value, unit, observed_at, source,
sample_type, verified. The layer is published only after every row passes QA.
"""
from __future__ import annotations

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import get_version, next_calver, set_version, sweep_stale_scores
from aia_etl.qa import FCT_BBOX

log = logging.getLogger(__name__)
settings = get_settings()

VALID_KINDS = {"land", "rent", "sale"}
VALID_SAMPLE_TYPES = {"listing", "transaction"}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "verified"}


def _parse_optional_int(value: str | None) -> int | None:
    if not value or not value.strip():
        return None
    return int(float(value))


def read_partner_csv(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            try:
                lon = float(row["lon"])
                lat = float(row["lat"])
                value = float(row["value"])
                kind = row["kind"].strip().lower()
                sample_type = row["sample_type"].strip().lower()
                observed_at = datetime.strptime(row["observed_at"], "%Y-%m-%d").date()
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid market row {line_no}: {exc}") from exc
            min_lon, min_lat, max_lon, max_lat = FCT_BBOX
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                raise ValueError(f"market row {line_no} falls outside the FCT pilot")
            if kind not in VALID_KINDS or sample_type not in VALID_SAMPLE_TYPES or value <= 0:
                raise ValueError(f"invalid market classification/value on row {line_no}")
            source = (row.get("source") or "").strip()
            if not source:
                raise ValueError(f"market row {line_no} has no partner source")
            records.append(
                {
                    "lon": lon,
                    "lat": lat,
                    "kind": kind,
                    "value": value,
                    "unit": (row.get("unit") or "").strip() or None,
                    "observed_at": observed_at,
                    "source": source,
                    "sample_type": sample_type,
                    "verified": _parse_bool(row.get("verified") or ""),
                    "external_id": (row.get("external_id") or row.get("pid") or "").strip()
                    or None,
                    "title": (row.get("title") or "").strip() or None,
                    "area": (row.get("area") or "").strip() or None,
                    "address": (row.get("address") or "").strip() or None,
                    "bedrooms": _parse_optional_int(row.get("bedrooms")),
                    "property_type": (row.get("property_type") or "").strip() or None,
                    "source_url": (row.get("source_url") or "").strip() or None,
                }
            )
    if not records:
        raise ValueError("partner market file contains no samples")
    return records


@app.task(name="aia_etl.tasks.market.refresh_market_samples")
def refresh_market_samples(csv_path: str | None = None) -> dict[str, Any]:
    path = Path(csv_path) if csv_path else Path(settings.data_dir) / "market" / "market_samples.csv"
    if not path.exists():
        log.info("market import skipped: %s is not available", path)
        return {"status": "skipped", "reason": "partner file unavailable", "path": str(path)}

    records = read_partner_csv(path)
    with connect() as conn:
        previous = get_version(conn, "market")
        version = next_calver(None if previous in (None, "unpublished") else previous)
        conn.execute(text("DELETE FROM market_samples"))
        conn.execute(
            text(
                """
                INSERT INTO market_samples (
                  geom, kind, value, unit, observed_at, source,
                  sample_type, verified, layer_version, external_id, title,
                  area, address, bedrooms, property_type, source_url
                ) VALUES (
                  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :kind, :value,
                  :unit, :observed_at, :source, :sample_type, :verified, :layer_version,
                  :external_id, :title, :area, :address, :bedrooms, :property_type,
                  :source_url
                )
                """
            ),
            [{**record, "layer_version": version} for record in records],
        )
        set_version(
            conn,
            "market",
            version,
            source="Partner agent network",
            notes=f"{len(records)} QA-passed geocoded listing/transaction samples",
        )
        invalidated = sweep_stale_scores(conn, "market", version)

    return {
        "status": "published",
        "version": version,
        "samples": len(records),
        "invalidated_scores": invalidated,
        "published_at": datetime.now(UTC).isoformat(),
    }

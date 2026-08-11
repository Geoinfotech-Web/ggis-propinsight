"""Verified official development-project ingestion for professional reports."""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection

from aia_etl.celery_app import app
from aia_etl.config import get_settings
from aia_etl.db import connect
from aia_etl.layers import bump_layer, next_layer_version

settings = get_settings()
OFFICIAL_HOSTS = {
    "fcta.gov.ng", "www.fcta.gov.ng", "projects.fcta.gov.ng",
    "nocopo.bpp.gov.ng", "budgetoffice.gov.ng", "www.budgetoffice.gov.ng",
}
ACTIVE_STAGES = {"budgeted", "procurement", "awarded", "ongoing"}


def classify_stage(value: str) -> str:
    text_value = value.strip().lower()
    if any(word in text_value for word in ("ongoing", "under construction", "implementation")):
        return "ongoing"
    if any(word in text_value for word in ("awarded", "contracted", "award")):
        return "awarded"
    if any(word in text_value for word in ("tender", "procurement", "bid")):
        return "procurement"
    if any(word in text_value for word in ("budget", "appropriat", "planned")):
        return "budgeted"
    raise ValueError(f"unsupported project lifecycle stage: {value!r}")


def _official_url(url: str) -> bool:
    return urlparse(url).hostname in OFFICIAL_HOSTS


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("project source date is required")
    return date.fromisoformat(value.strip()[:10])


def normalise_project(raw: dict[str, Any], feed_url: str) -> dict[str, Any]:
    source_url = str(raw.get("source_url") or feed_url)
    if not _official_url(source_url):
        raise ValueError(f"project source is not an approved official host: {source_url}")
    name = str(raw.get("name") or raw.get("title") or "").strip()
    location_text = str(raw.get("location_text") or raw.get("location") or "").strip()
    authority = str(raw.get("authority") or raw.get("procuring_entity") or "").strip()
    if not name or not location_text or not authority:
        raise ValueError("project requires name, authority and location_text")
    stage = classify_stage(str(raw.get("lifecycle_stage") or raw.get("status") or ""))
    published = _parse_date(raw.get("source_published_at") or raw.get("date"))
    lon = raw.get("lon") or raw.get("longitude")
    lat = raw.get("lat") or raw.get("latitude")
    confidence = raw.get("geocoding_confidence")
    precision = str(raw.get("location_precision") or "unresolved").lower()
    if lon is not None and lat is not None and precision == "unresolved":
        precision = "exact"
        confidence = 1.0 if confidence is None else confidence
    official_id = str(raw.get("official_id") or raw.get("ocid") or "").strip()
    if not official_id:
        official_id = hashlib.sha256(
            f"{authority}|{name}|{published}|{location_text}".encode()
        ).hexdigest()[:32]
    return {
        "official_id": official_id, "name": name, "authority": authority,
        "agency": raw.get("agency"),
        "sector": str(raw.get("sector") or "other").strip().lower(),
        "lifecycle_stage": stage, "status": raw.get("status"),
        "budget_ngn": float(raw["budget_ngn"]) if raw.get("budget_ngn") not in (None, "") else None,
        "location_text": location_text, "ward": raw.get("ward"),
        "area_council": raw.get("area_council"),
        "lon": float(lon) if lon is not None else None,
        "lat": float(lat) if lat is not None else None,
        "location_precision": precision,
        "geocoding_confidence": float(confidence) if confidence is not None else None,
        "source_url": source_url, "source_published_at": published,
        "source_updated_at": (
            _parse_date(raw["source_updated_at"])
            if raw.get("source_updated_at")
            else None
        ),
        "verified_at": datetime.now(UTC), "active": stage in ACTIVE_STAGES,
    }


def fetch_feed(url: str) -> list[dict[str, Any]]:
    if not _official_url(url):
        raise ValueError(f"feed is not hosted on an approved official domain: {url}")
    response = httpx.get(url, follow_redirects=True, timeout=90.0)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type or url.lower().endswith(".json"):
        body = response.json()
        if isinstance(body, list):
            return body
        for key in ("projects", "records", "releases", "data"):
            if isinstance(body, dict) and isinstance(body.get(key), list):
                return body[key]
        raise ValueError("official JSON feed has no recognised project list")
    if "csv" in content_type or url.lower().endswith(".csv"):
        return list(csv.DictReader(io.StringIO(response.text)))
    raise ValueError("official project feed must be a structured JSON or CSV export")


def publish_projects(conn: Connection, records: list[dict[str, Any]], layer_version: str) -> int:
    if not records:
        raise ValueError("no valid official project records to publish")
    conn.execute(text("UPDATE development_projects SET active = FALSE"))
    statement = text(
        """
        INSERT INTO development_projects (
          official_id, name, authority, agency, sector, lifecycle_stage, status,
          budget_ngn, location_text, ward, area_council, geom, location_precision,
          geocoding_confidence, source_url, source_published_at, source_updated_at,
          verified_at, active, layer_version
        ) VALUES (
          :official_id, :name, :authority, :agency, :sector, :lifecycle_stage, :status,
          :budget_ngn, :location_text, :ward, :area_council,
          CASE WHEN :lon IS NULL OR :lat IS NULL THEN NULL
            ELSE ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) END,
          :location_precision, :geocoding_confidence, :source_url,
          :source_published_at, :source_updated_at, :verified_at, :active, :layer_version
        ) ON CONFLICT (official_id) DO UPDATE SET
          name=EXCLUDED.name, authority=EXCLUDED.authority, agency=EXCLUDED.agency,
          sector=EXCLUDED.sector, lifecycle_stage=EXCLUDED.lifecycle_stage,
          status=EXCLUDED.status, budget_ngn=EXCLUDED.budget_ngn,
          location_text=EXCLUDED.location_text, ward=EXCLUDED.ward,
          area_council=EXCLUDED.area_council, geom=EXCLUDED.geom,
          location_precision=EXCLUDED.location_precision,
          geocoding_confidence=EXCLUDED.geocoding_confidence,
          source_url=EXCLUDED.source_url, source_published_at=EXCLUDED.source_published_at,
          source_updated_at=EXCLUDED.source_updated_at, verified_at=EXCLUDED.verified_at,
          active=EXCLUDED.active, layer_version=EXCLUDED.layer_version
        """
    )
    conn.execute(statement, [{**record, "layer_version": layer_version} for record in records])
    return len(records)


@app.task(name="aia_etl.tasks.projects.refresh_development_projects")
def refresh_development_projects(feed_urls: list[str] | None = None) -> dict[str, Any]:
    """Refresh reviewed structured exports from FCTA, NOCOPO and Budget Office."""
    urls = feed_urls or settings.official_projects_feeds
    if not urls:
        raise RuntimeError("OFFICIAL_PROJECTS_FEED_URLS has no structured official feeds")
    records: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for url in urls:
        try:
            records.extend(normalise_project(item, url) for item in fetch_feed(url))
        except Exception as exc:  # noqa: BLE001
            errors[url] = str(exc)
    if not records:
        raise RuntimeError(f"no official project feed produced publishable records: {errors}")
    deduplicated = {record["official_id"]: record for record in records}
    with connect() as conn:
        version = next_layer_version(conn, "projects")
        count = publish_projects(conn, list(deduplicated.values()), version)
        published, invalidated = bump_layer(
            conn, "projects", source="FCTA + NOCOPO + Federal Budget Office",
            notes="Structured official records only; stage and location precision preserved",
        )
        if published != version:
            raise RuntimeError("projects layer version changed during publication")
    return {"status": "published", "version": version, "project_count": count,
            "feed_errors": errors, "scores_invalidated": invalidated}

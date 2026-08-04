"""Groundwork Data Abuja Housing v1 market-listing adapter.

The CC BY 4.0 source contains area names rather than coordinates. Records are
assigned to QA-reviewed locality centroids, then filtered with the thresholds
documented in ``docs/Groundwork Abuja Housing v1 QA.md``. These coordinates are
area-level evidence only and must never be presented as parcel locations.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from statistics import median
from typing import Any

import httpx

GROUNDWORK_MARKET_URL = (
    "https://huggingface.co/datasets/ayookuns/abuja-housing-prices-v1/"
    "resolve/main/groundwork_abuja_housing_v1.csv"
)

# QA-reviewed OSM/Nominatim locality centroids (lon, lat). Apo, Dawaki and
# Karsana were intentionally excluded because their automated matches were
# ambiguous or absent during the documented QA run.
AREA_CENTROIDS: dict[str, tuple[float, float]] = {
    "Asokoro": (7.5196863, 9.0423462),
    "Galadimawa": (7.4305560, 8.9847220),
    "Guzape": (7.5072730, 9.0112476),
    "Gwarinpa": (7.3929654, 9.1098210),
    "Jabi": (7.4210076, 9.0646229),
    "Katampe": (7.4617179, 9.1028513),
    "Kubwa": (7.3410781, 9.1526752),
    "Life-Camp": (7.4040774, 9.0674684),
    "Lokogoma": (7.4732799, 8.9664033),
    "Lugbe": (7.3574905, 8.9910376),
    "Maitama": (7.4908053, 9.0900989),
    "Utako": (7.4435303, 9.0691100),
    "Wuse-2": (7.4665551, 9.0620454),
}


def _observed_at(row: dict[str, str]) -> date:
    value = (row.get("last_updated") or row.get("date_added") or "").strip()
    return datetime.strptime(value, "%d-%b-%y").date()


def qa_groundwork_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Validate, geocode and price-filter raw Groundwork listing rows."""
    required = {
        "title",
        "price_ngn",
        "listing_type",
        "area",
        "address",
        "bedrooms",
        "property_type",
        "pid",
        "date_added",
        "source_url",
    }
    if not rows:
        raise ValueError("Groundwork market source returned no rows")
    missing = required - rows[0].keys()
    if missing:
        raise ValueError(f"Groundwork market source is missing columns: {sorted(missing)}")

    seen_ids: set[str] = set()
    geocoded: list[tuple[dict[str, str], float]] = []
    for line_no, row in enumerate(rows, start=2):
        listing_id = row["pid"].strip()
        if not listing_id or listing_id in seen_ids:
            raise ValueError(f"missing or duplicate listing ID on source row {line_no}")
        seen_ids.add(listing_id)
        if not all((row.get(field) or "").strip() for field in required):
            raise ValueError(f"missing required market value on source row {line_no}")
        kind = row["listing_type"].strip().lower()
        if kind not in {"rent", "sale"}:
            raise ValueError(f"invalid listing type on source row {line_no}: {kind!r}")
        try:
            price = float(row["price_ngn"])
            _observed_at(row)
        except ValueError as exc:
            raise ValueError(f"invalid price/date on source row {line_no}: {exc}") from exc
        if row["area"].strip() in AREA_CENTROIDS:
            geocoded.append((row, price))

    grouped_prices: dict[tuple[str, str], list[float]] = {}
    for row, price in geocoded:
        key = (row["area"].strip(), row["listing_type"].strip().lower())
        grouped_prices.setdefault(key, []).append(price)

    accepted: list[dict[str, Any]] = []
    for row, price in geocoded:
        area = row["area"].strip()
        kind = row["listing_type"].strip().lower()
        group_median = median(grouped_prices[(area, kind)])
        absolute_ok = (
            500_000 <= price <= 100_000_000
            if kind == "rent"
            else 5_000_000 <= price <= 5_000_000_000
        )
        if not absolute_ok or not 0.15 * group_median <= price <= 6 * group_median:
            continue
        lon, lat = AREA_CENTROIDS[area]
        accepted.append(
            {
                "lon": lon,
                "lat": lat,
                "kind": kind,
                "value": price,
                "unit": "NGN/year" if kind == "rent" else "NGN",
                "observed_at": _observed_at(row),
                "source": "Groundwork Data / PropertyPro.ng",
                "sample_type": "listing",
                "verified": False,
                "external_id": row["pid"].strip(),
                "title": row["title"].strip(),
                "area": area,
                "address": row["address"].strip(),
                "bedrooms": int(float(row["bedrooms"])),
                "property_type": row["property_type"].strip(),
                "source_url": row["source_url"].strip(),
            }
        )
    if not accepted:
        raise ValueError("Groundwork market source has no rows after QA")
    return accepted


def fetch_groundwork_market(url: str = GROUNDWORK_MARKET_URL) -> list[dict[str, Any]]:
    """Download the licensed CSV and return publication-ready records."""
    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    return qa_groundwork_rows(rows)

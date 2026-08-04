"""Tests for the licensed Groundwork Abuja market adapter."""
from __future__ import annotations

from aia_etl.sources.groundwork_market import qa_groundwork_rows


def _row(pid: str, area: str, kind: str, price: int) -> dict[str, str]:
    return {
        "title": "3 Bedroom Flat",
        "price_ngn": str(price),
        "listing_type": kind,
        "area": area,
        "neighbourhood": area,
        "address": f"{area}, Abuja",
        "bedrooms": "3",
        "bathrooms": "3",
        "toilets": "4",
        "property_type": "Flat/Apartment",
        "description": "",
        "pid": pid,
        "date_added": "01-Apr-26",
        "last_updated": "24-Apr-26",
        "source_url": f"https://example.test/{pid}",
    }


def test_groundwork_qa_geocodes_and_normalises_licensed_listings():
    rows = [
        _row("rent-1", "Jabi", "rent", 5_000_000),
        _row("rent-2", "Jabi", "rent", 6_000_000),
        _row("sale-1", "Jabi", "sale", 200_000_000),
        _row("excluded", "Dawaki", "rent", 4_000_000),
    ]

    records = qa_groundwork_rows(rows)

    assert len(records) == 3
    assert {record["external_id"] for record in records} == {"rent-1", "rent-2", "sale-1"}
    assert {record["unit"] for record in records} == {"NGN/year", "NGN"}
    assert all(record["source"].startswith("Groundwork Data") for record in records)
    assert all(record["verified"] is False for record in records)


def test_groundwork_qa_rejects_relative_and_absolute_price_outliers():
    rows = [
        _row("normal-1", "Jabi", "sale", 200_000_000),
        _row("normal-2", "Jabi", "sale", 250_000_000),
        _row("normal-3", "Jabi", "sale", 300_000_000),
        _row("outlier", "Jabi", "sale", 2_000_000_000),
    ]

    records = qa_groundwork_rows(rows)

    assert {record["external_id"] for record in records} == {
        "normal-1",
        "normal-2",
        "normal-3",
    }

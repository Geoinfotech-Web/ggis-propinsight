"""Lightweight QA-rule framework for ETL records (TDD §4.6).

Each pipeline runs its records through a set of rules before publishing. A record
that fails any rule is rejected (kept out of the published layer) and reported.
The rules are pure functions so they're unit-testable without a database.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from aia_etl.poi_categories import AIA_CATEGORIES

Record = dict[str, Any]
Rule = Callable[[Record], str | None]  # returns an error message, or None if OK


@dataclass
class QAReport:
    passed: list[Record] = field(default_factory=list)
    rejected: list[tuple[Record, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.passed) + len(self.rejected)

    @property
    def reject_rate(self) -> float:
        return len(self.rejected) / self.total if self.total else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": len(self.passed),
            "rejected": len(self.rejected),
            "reject_rate": round(self.reject_rate, 4),
        }


# --- Reusable rules --------------------------------------------------------
def require_geometry(rec: Record) -> str | None:
    if not rec.get("geom") and not rec.get("lon") and not rec.get("lat"):
        return "missing geometry"
    return None


def valid_category(rec: Record) -> str | None:
    cat = rec.get("category")
    if cat is not None and cat not in AIA_CATEGORIES:
        return f"invalid category {cat!r}"
    return None


def within_bbox(bbox: tuple[float, float, float, float]) -> Rule:
    """Factory: reject points outside (min_lon, min_lat, max_lon, max_lat)."""
    min_lon, min_lat, max_lon, max_lat = bbox

    def _rule(rec: Record) -> str | None:
        lon, lat = rec.get("lon"), rec.get("lat")
        if lon is None or lat is None:
            return None  # geometry rule handles missing coords
        if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
            return "outside AOI bbox"
        return None

    return _rule


def run_rules(records: Iterable[Record], rules: list[Rule]) -> QAReport:
    report = QAReport()
    for rec in records:
        error = next((msg for r in rules if (msg := r(rec)) is not None), None)
        if error is None:
            report.passed.append(rec)
        else:
            report.rejected.append((rec, error))
    return report


# Approximate FCT (Abuja) bounding box for the pilot AOI QA gate.
FCT_BBOX = (6.75, 8.25, 7.75, 9.35)

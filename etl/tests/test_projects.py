"""Official project validation and lifecycle tests."""
from __future__ import annotations

import pytest

from aia_etl.tasks.projects import classify_stage, normalise_project


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026 appropriation", "budgeted"),
        ("open tender", "procurement"),
        ("contract awarded", "awarded"),
        ("ongoing implementation", "ongoing"),
    ],
)
def test_project_lifecycle_is_explicit(raw, expected):  # noqa: ANN001
    assert classify_stage(raw) == expected


def test_budget_record_is_not_described_as_under_construction():
    record = normalise_project(
        {
            "official_id": "FCTA-1",
            "name": "District road",
            "authority": "FCTA",
            "location_text": "Bwari",
            "status": "2026 budget allocation",
            "source_published_at": "2026-01-02",
        },
        "https://fcta.gov.ng/projects.json",
    )
    assert record["lifecycle_stage"] == "budgeted"
    assert record["active"] is True


def test_non_official_project_source_is_rejected():
    with pytest.raises(ValueError, match="approved official host"):
        normalise_project(
            {
                "name": "Proposed estate",
                "authority": "Unknown",
                "location_text": "Abuja",
                "status": "ongoing",
                "source_published_at": "2026-01-02",
            },
            "https://example.com/projects.json",
        )

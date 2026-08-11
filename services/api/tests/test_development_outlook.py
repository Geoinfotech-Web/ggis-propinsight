"""Professional development-outlook formula tests."""
from app.location_intelligence.development_outlook import (
    MIGRATION_ADVISORY,
    migration_pressure,
)
from app.location_intelligence.personas import fit_score


def test_migration_pressure_uses_sixty_forty_components():
    result = migration_pressure(80.0, 50.0)
    assert result is not None
    assert result["index"] == 68.0
    assert result["band"] == "Moderate"
    assert result["confidence"] == "Medium"
    assert result["advisory"] == MIGRATION_ADVISORY


def test_migration_pressure_reweights_one_available_component():
    result = migration_pressure(75.0, None)
    assert result is not None
    assert result["index"] == 75.0
    assert result["band"] == "High"
    assert result["confidence"] == "Low"


def test_migration_pressure_boundaries_and_unavailable():
    assert migration_pressure(39.9, None)["band"] == "Low"  # type: ignore[index]
    assert migration_pressure(40.0, None)["band"] == "Moderate"  # type: ignore[index]
    assert migration_pressure(70.0, None)["band"] == "High"  # type: ignore[index]
    assert migration_pressure(None, None) is None


def test_outlook_context_cannot_change_fit_score():
    domains = {"market": {"score": 80.0, "included_in_fit": True}}
    before = fit_score(domains, "investor")
    unrelated_outlook = {"migration_pressure": {"index": 0}, "projects": {"returned_count": 0}}
    assert unrelated_outlook
    assert fit_score(domains, "investor") == before

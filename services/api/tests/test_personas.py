"""Unit tests for persona domain weights, exclusions, and fit_score."""
from __future__ import annotations

from types import SimpleNamespace

from app.location_intelligence.personas import (
    PERSONAS,
    domain_priority,
    domain_suitability_score,
    filter_domains_for_persona,
    fit_score,
    included_domains,
    resolve_persona_key,
)


def test_persona_weights_sum_to_one():
    for key, persona in PERSONAS.items():
        total = sum(persona["domain_weights"].values())
        assert abs(total - 1.0) < 1e-9, f"{key} weights sum to {total}"


def test_legacy_fct_v1_maps_to_home_buyer():
    assert resolve_persona_key("fct-v1") == "home_buyer"
    assert resolve_persona_key("investor") == "investor"
    assert resolve_persona_key("unknown") == "home_buyer"


def test_domain_priority_investor_leads_with_market():
    assert domain_priority("investor")[0] == "market"
    assert domain_priority("developer")[0] == "feasibility"
    assert domain_priority("home_buyer")[0] == "flood"


def test_buyer_and_tenant_exclude_planning_and_feasibility():
    for persona in ("home_buyer", "tenant"):
        assert "feasibility" not in included_domains(persona)
        assert "feasibility" not in domain_priority(persona)
        assert "tenure" not in included_domains(persona)
        assert "tenure" not in domain_priority(persona)


def test_investor_and_developer_include_feasibility():
    assert "feasibility" in included_domains("investor")
    assert "feasibility" in included_domains("developer")


def test_filter_domains_for_persona_drops_excluded():
    domains = {
        "flood": SimpleNamespace(score=80.0),
        "feasibility": SimpleNamespace(score=40.0),
        "tenure": SimpleNamespace(score=90.0),
        "amenities": SimpleNamespace(score=60.0),
    }
    filtered = filter_domains_for_persona(domains, "home_buyer")
    assert "feasibility" not in filtered
    assert set(filtered) == {"flood", "amenities"}


def test_fit_score_renormalises_over_present_domains():
    # Flood and amenities have equal weight for home_buyer, so the fit is 50.
    domains = {
        "flood": SimpleNamespace(score=100.0),
        "amenities": SimpleNamespace(score=0.0),
        "security": SimpleNamespace(score=None),
    }
    assert fit_score(domains, "home_buyer") == 50.0


def test_fit_score_ignores_excluded_domain_even_if_present():
    domains = {
        "flood": SimpleNamespace(score=100.0),
        "feasibility": SimpleNamespace(score=0.0),
    }
    # feasibility not in home_buyer weights → fit is just flood = 100
    assert fit_score(domains, "home_buyer") == 100.0


def test_fit_score_none_when_no_scores():
    domains = {"flood": SimpleNamespace(score=None)}
    assert fit_score(domains, "tenant") is None


def test_flood_hazard_is_inverted_for_fit():
    domains = {
        "flood": SimpleNamespace(
            score=80.0,
            score_direction="higher_is_worse",
            included_in_fit=True,
        ),
        "amenities": SimpleNamespace(score=100.0),
    }
    # Equal home-buyer weights: flood suitability 20 and amenities 100 -> fit 60.
    assert domain_suitability_score("flood", domains["flood"]) == 20.0
    assert fit_score(domains, "home_buyer") == 60.0


def test_excluded_domain_is_renormalised_out_of_fit():
    domains = {
        "flood": SimpleNamespace(
            score=90.0,
            score_direction="higher_is_worse",
            included_in_fit=False,
        ),
        "amenities": SimpleNamespace(score=75.0),
    }
    assert fit_score(domains, "home_buyer") == 75.0

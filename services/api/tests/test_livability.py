"""Environmental livability scoring regression tests."""
from app.location_intelligence.livability import livability_rating, score_livability


def test_livability_uses_documented_environmental_weights():
    result = score_livability(
        green_share=1.0,
        heat_percentile=0.0,
        built_bare_share=0.0,
    )
    assert result.score == 100.0
    assert set(result.indicators) == {
        "green_cover",
        "surface_heat",
        "environmental_pressure",
    }


def test_livability_inverts_heat_and_pressure():
    comfortable = score_livability(
        green_share=0.8, heat_percentile=0.1, built_bare_share=0.1
    )
    stressed = score_livability(
        green_share=0.1, heat_percentile=0.9, built_bare_share=0.9
    )
    assert comfortable.score is not None and stressed.score is not None
    assert comfortable.score > stressed.score


def test_livability_ratings_use_plain_environmental_language():
    assert livability_rating(70) == "Favourable environment"
    assert livability_rating(40) == "Mixed conditions"
    assert livability_rating(39.9) == "High environmental pressure"
    assert livability_rating(None) is None

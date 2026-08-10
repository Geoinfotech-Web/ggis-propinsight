"""Persona-aware, plain-language insight for the overall scorecard."""
from __future__ import annotations

from typing import Any

from app.location_intelligence.personas import domain_suitability_score

# Shared 0..100 quality bands (align with the map legend + score-bar colours).
STRONG = 70.0
MODERATE = 40.0

DOMAIN_WORDS: dict[str, str] = {
    "flood": "flood risk",
    "security": "safety",
    "amenities": "nearby amenities",
    "accessibility": "road access",
    "tenure": "land status",
    "market": "market value",
    "livability": "livability",
    "feasibility": "buildability",
}

CONSUMER_OPENINGS: dict[str, dict[str, str]] = {
    "home_buyer": {
        "strong": "This area looks like a strong choice for buying a home",
        "solid": "This area looks like a good choice for buying a home",
        "mixed": "This area may work for buying a home, but check the trade-offs",
        "weak": "This area has concerns to resolve before buying a home",
        "unknown": "There is not enough information yet to judge this area for buying a home",
    },
    "tenant": {
        "strong": "This area looks like a strong option for renting",
        "solid": "This area looks like a good option for renting",
        "mixed": "This area may suit some renters, but check the trade-offs",
        "weak": "This area may be difficult for comfortable day-to-day renting",
        "unknown": "There is not enough information yet to judge this area for renting",
    },
}

HIGHLIGHT_TITLES: dict[str, str] = {
    "flood": "Flooding",
    "security": "Safety",
    "amenities": "Everyday essentials",
    "accessibility": "Getting around",
    "tenure": "Planning and land status",
    "market": "Rent costs",
    "livability": "Neighbourhood comfort",
    "feasibility": "Buildability",
}

HIGHLIGHT_COPY: dict[str, dict[str, str]] = {
    "flood": {
        "positive": "Current information suggests lower flood concern here.",
        "neutral": "Flood conditions are mixed; check the area after heavy rain.",
        "caution": "Flooding needs closer checking before you decide.",
    },
    "security": {
        "positive": "The available local safety indicators are encouraging.",
        "neutral": "Safety looks mixed; ask residents about different times of day.",
        "caution": "Safety needs closer local checks, especially at night.",
    },
    "amenities": {
        "positive": "Useful shops, schools or clinics are relatively accessible.",
        "neutral": "Some everyday services are nearby, but trips may vary.",
        "caution": "Everyday services may require longer or less convenient trips.",
    },
    "accessibility": {
        "positive": "Road access and key journeys look relatively convenient.",
        "neutral": "Travel is workable, but test the commute at busy times.",
        "caution": "Daily travel may be difficult or time-consuming.",
    },
    "tenure": {
        "positive": "Available planning signals are comparatively favourable.",
        "neutral": "Planning status needs normal document checks.",
        "caution": "Planning or land-status questions need closer verification.",
    },
    "market": {
        "positive": "Nearby price evidence is comparatively favourable.",
        "neutral": "Prices are mixed; compare several similar properties.",
        "caution": "Price or value needs careful comparison before committing.",
    },
    "livability": {
        "positive": "The area looks more comfortable for everyday living.",
        "neutral": "Neighbourhood comfort is mixed; visit at different times.",
        "caution": "Check noise, utilities and neighbourhood comfort in person.",
    },
    "feasibility": {
        "positive": "Available terrain and access signals look more buildable.",
        "neutral": "Buildability is mixed and needs a site assessment.",
        "caution": "Site conditions may add cost or development constraints.",
    },
}


def quality_band(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= STRONG:
        return "Strong"
    if score >= MODERATE:
        return "Moderate"
    return "Weak"


def _fit_phrase(fit: float | None) -> str:
    if fit is None:
        return "Not enough data yet to rate this location"
    if fit >= 75:
        return "A strong match"
    if fit >= 60:
        return "A solid match"
    if fit >= 40:
        return "A mixed match"
    return "A weak match"


def _consumer_fit_band(fit: float | None) -> str:
    if fit is None:
        return "unknown"
    if fit >= 75:
        return "strong"
    if fit >= 60:
        return "solid"
    if fit >= 40:
        return "mixed"
    return "weak"


def _word(domain: str) -> str:
    return DOMAIN_WORDS.get(domain, domain)


def _persona_phrase(persona_label: str, fit: float | None) -> str:
    article = "an" if persona_label[:1].lower() in "aeiou" else "a"
    return f"{_fit_phrase(fit)} for {article} {persona_label}"


def _scored_domains(domains: dict[str, Any]) -> list[tuple[str, float]]:
    scored: list[tuple[str, float]] = []
    for name, result in domains.items():
        score = domain_suitability_score(name, result)
        if score is not None:
            scored.append((name, float(score)))
    return scored


def _consumer_summary(
    persona_key: str,
    fit: float | None,
    scored: list[tuple[str, float]],
) -> str:
    opening = CONSUMER_OPENINGS[persona_key][_consumer_fit_band(fit)]
    if not scored:
        return f"{opening}. More local information is needed before relying on this report."
    return f"{opening}. Here is what supports the result and what you should check."


def build_summary(
    persona_key: str,
    persona_label: str,
    fit: float | None,
    domains: dict[str, Any],
) -> str:
    """Return a relatable consumer summary or concise professional summary."""
    scored = _scored_domains(domains)
    if persona_key in CONSUMER_OPENINGS:
        return _consumer_summary(persona_key, fit, scored)

    phrase = _persona_phrase(persona_label, fit)
    if not scored:
        return f"{phrase}. Scores appear as data layers publish."

    best = max(scored, key=lambda item: item[1])
    worst = min(scored, key=lambda item: item[1])

    strength = (
        "lower flood risk" if best[0] == "flood" else f"strongest on {_word(best[0])}"
    )
    parts = [phrase, strength]
    if worst[0] != best[0] and worst[1] < STRONG:
        parts.append(f"watch {_word(worst[0])}")
    return " — ".join([parts[0], ", ".join(parts[1:])]) + "."


def _highlight_tone(score: float) -> str:
    if score >= STRONG:
        return "positive"
    if score < MODERATE:
        return "caution"
    return "neutral"


def _highlight_copy(domain: str, tone: str, persona_key: str) -> str:
    if domain == "market" and persona_key == "tenant":
        return {
            "positive": "Nearby rent information is comparatively favourable.",
            "neutral": "Compare the full rent and service charges for similar homes.",
            "caution": "Rent and service charges need careful comparison before paying.",
        }[tone]
    if domain == "market" and persona_key == "home_buyer":
        return {
            "positive": "Nearby purchase-price information is comparatively favourable.",
            "neutral": "Compare recent prices for several similar homes before offering.",
            "caution": "The purchase price needs careful comparison before offering.",
        }[tone]
    return HIGHLIGHT_COPY[domain][tone]


def _result_value(result: Any, key: str, default: Any = None) -> Any:
    if hasattr(result, key):
        return getattr(result, key)
    if isinstance(result, dict):
        return result.get(key, default)
    return default


def build_highlights(
    persona_key: str,
    domains: dict[str, Any],
    priority: list[str],
) -> list[dict[str, str]]:
    """Select three readable takeaways: strongest, weakest, then priority."""
    scored = _scored_domains(domains)
    if not scored:
        return []

    ordered_names: list[str] = []
    best = max(scored, key=lambda item: item[1])[0]
    worst = min(scored, key=lambda item: item[1])[0]
    ordered_names.append(best)
    if worst != best:
        ordered_names.append(worst)
    ordered_names.extend(name for name in priority if name not in ordered_names)

    scores = dict(scored)
    highlights: list[dict[str, str]] = []
    for name in ordered_names:
        if name not in scores or name not in HIGHLIGHT_COPY:
            continue
        tone = _highlight_tone(scores[name])
        title = HIGHLIGHT_TITLES[name]
        if name == "market" and persona_key == "home_buyer":
            title = "Purchase prices"
        elif name == "market" and persona_key in {"investor", "developer"}:
            title = "Market value"
        copy = _highlight_copy(name, tone, persona_key)
        if name == "flood":
            rating = _result_value(domains[name], "rating")
            if isinstance(rating, str) and rating.strip():
                copy = f"GGIS currently classifies this location as {rating.strip().lower()}."
            title = "Flood risk"
        highlights.append(
            {
                "domain": name,
                "title": title,
                "text": copy,
                "tone": tone,
            }
        )
        if len(highlights) == 3:
            break
    return highlights

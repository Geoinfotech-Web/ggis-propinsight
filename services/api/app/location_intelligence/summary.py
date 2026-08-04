"""Short, plain-language insight for the overall scorecard (public-facing)."""
from __future__ import annotations

from typing import Any

# Shared 0..100 quality bands (align with the map legend + score-bar colours).
STRONG = 70.0
MODERATE = 40.0

DOMAIN_WORDS: dict[str, str] = {
    "flood": "flood safety",
    "security": "safety",
    "amenities": "nearby amenities",
    "accessibility": "road access",
    "tenure": "land status",
    "market": "market value",
    "livability": "livability",
    "feasibility": "buildability",
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


def _word(domain: str) -> str:
    return DOMAIN_WORDS.get(domain, domain)


def build_summary(persona_label: str, fit: float | None, domains: dict[str, Any]) -> str:
    """One-liner: fit verdict + top strength + main thing to watch."""
    scored: list[tuple[str, float]] = []
    for name, result in domains.items():
        score = result.score if hasattr(result, "score") else result.get("score")
        if score is not None:
            scored.append((name, float(score)))

    phrase = f"{_fit_phrase(fit)} for a {persona_label}"
    if not scored:
        return f"{phrase}. Scores appear as data layers publish."

    best = max(scored, key=lambda kv: kv[1])
    worst = min(scored, key=lambda kv: kv[1])

    parts = [phrase]
    parts.append(f"strongest on {_word(best[0])}")
    # Only flag a concern when it's genuinely weak and not the same as the best.
    if worst[0] != best[0] and worst[1] < STRONG:
        parts.append(f"watch {_word(worst[0])}")
    return " — ".join([parts[0], ", ".join(parts[1:])]) + "."

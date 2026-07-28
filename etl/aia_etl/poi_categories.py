"""Map OSM tags to AIA POI categories.

AIA categories (schema v1 `poi.category`):
    school | hospital | water | power | isp | market | bank | fuel | worship

Only tags that map to one of these are ingested; everything else is dropped so
the amenity layer stays aligned to the questions the scorecard answers.
"""
from __future__ import annotations

AIA_CATEGORIES = (
    "school",
    "hospital",
    "water",
    "power",
    "isp",
    "market",
    "bank",
    "fuel",
    "worship",
)

# (osm_key, osm_value) -> AIA category. Ordered by specificity where it matters.
_TAG_MAP: dict[tuple[str, str], str] = {
    # Education
    ("amenity", "school"): "school",
    ("amenity", "kindergarten"): "school",
    ("amenity", "college"): "school",
    ("amenity", "university"): "school",
    # Health
    ("amenity", "hospital"): "hospital",
    ("amenity", "clinic"): "hospital",
    ("amenity", "doctors"): "hospital",
    ("amenity", "pharmacy"): "hospital",
    ("healthcare", "hospital"): "hospital",
    # Water
    ("man_made", "water_well"): "water",
    ("man_made", "water_works"): "water",
    ("amenity", "drinking_water"): "water",
    ("man_made", "borehole"): "water",
    # Power
    ("power", "substation"): "power",
    ("power", "transformer"): "power",
    ("power", "plant"): "power",
    # Markets & daily-life retail
    ("amenity", "marketplace"): "market",
    ("shop", "supermarket"): "market",
    ("shop", "mall"): "market",
    # Banking
    ("amenity", "bank"): "bank",
    ("amenity", "atm"): "bank",
    # Fuel
    ("amenity", "fuel"): "fuel",
    # Worship
    ("amenity", "place_of_worship"): "worship",
}


def categorize(tags: dict[str, str]) -> str | None:
    """Return the AIA category for an OSM feature's tags, or None if not relevant."""
    for key, value in tags.items():
        cat = _TAG_MAP.get((key, value))
        if cat:
            return cat
    # ISP/telecom mast fallback (value varies): towers tagged as communication.
    if tags.get("man_made") == "mast" and tags.get("tower:type") == "communication":
        return "isp"
    return None


# Reverse index: which OSM key/values feed each category (used to build osm2pgsql
# style filters and to document coverage).
def osm_selectors_for(category: str) -> list[tuple[str, str]]:
    return [pair for pair, cat in _TAG_MAP.items() if cat == category]

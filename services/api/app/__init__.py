"""GGIS PropInsight (AIA) API — modular monolith.

Service modules (flood, location_intelligence, scoring, accessibility, reports,
community, ai_assistant) live as internal packages and are composed behind a
single FastAPI gateway. They are split into independently deployable services
only where scaling or ownership later demands it (TDD §1.4).
"""

__version__ = "0.1.0"

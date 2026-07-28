"""GGIS Flood Watch integration package.

AIA never re-derives flood risk locally (TDD §5.3). It consumes the GGIS Flood
Watch service exclusively; when GGIS is unreachable the flood domain degrades
gracefully to a timestamped last-known class rather than failing the scorecard.
"""

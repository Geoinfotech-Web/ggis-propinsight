"""Location Intelligence service — orchestrates the eight-domain scorecard.

The core interaction (TDD §2.2): a point/polygon fans out in parallel to
PostGIS spatial queries, the Accessibility service, and a live GGIS Flood Watch
risk query; the Scoring Engine normalises and weights the results; the response
is cached in Redis (geohash + layer versions) and returned as a JSON scorecard.
"""

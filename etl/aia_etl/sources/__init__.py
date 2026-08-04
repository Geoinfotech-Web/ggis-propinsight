"""Multi-source POI ingestion (Overview §6.3).

AIA is not limited to OpenStreetMap. This package normalises POIs from any open
provider into the shared `poi` schema, tagged with a `source` so provenance is
preserved and per-source refreshes are independent:

  * overpass  — OpenStreetMap via the Overpass API (comprehensive, no bulk download)
  * overture  — Overture Maps Places (open, aggregates many non-OSM sources)
  * (extend)  — agency registries / ArcGIS FeatureServers via `registry_geojson`

Each adapter returns `PoiRecord`s; `replace_source_pois` publishes them. The
`poi` layer version bumps on publish, invalidating dependent cached scorecards.
"""

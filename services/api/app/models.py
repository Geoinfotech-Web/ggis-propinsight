"""PostGIS schema v1 (TDD §6.1).

All geometry columns are SRID 4326. GiST indexes on every geom; geography-cast
KNN is used for proximity queries; poi(category) carries a partial index.
Every published layer bump changes `layer_version`, which invalidates dependent
cached scores via a Celery sweep.
"""
from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

SRID = 4326


class District(Base):
    """Admin & analysis units. Security and reviews aggregate to this level."""

    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(80), index=True)
    density_class: Mapped[str | None] = mapped_column(String(20))  # high|medium|low
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))


class Ward(Base):
    """GRID3 operational ward used for local context and safe aggregation."""

    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    state_code: Mapped[str | None] = mapped_column(ForeignKey("states.code"), index=True)
    lga_id: Mapped[int | None] = mapped_column(ForeignKey("lgas.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    area_council: Mapped[str] = mapped_column(String(160), index=True)
    state: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_version: Mapped[str | None] = mapped_column(String(40))
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Location(Base):
    """Saved/analysed areas of interest (points or drawn polygons)."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geom: Mapped[object] = mapped_column(Geometry(srid=SRID))  # Point or Polygon
    geohash8: Mapped[str] = mapped_column(String(8), index=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Poi(Base):
    """Amenities. category ∈ school|hospital|water|power|isp|market|bank|fuel|worship."""

    __tablename__ = "poi"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=SRID))
    category: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str | None] = mapped_column(String(80))
    verified: Mapped[bool] = mapped_column(default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    layer_version: Mapped[str] = mapped_column(String(20), index=True)


class Road(Base):
    """Road centreline for accessibility proximity (OSM-derived)."""

    __tablename__ = "roads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geom: Mapped[object] = mapped_column(Geometry("LINESTRING", srid=SRID))
    highway: Mapped[str | None] = mapped_column(String(40))
    name: Mapped[str | None] = mapped_column(String(200))
    layer_version: Mapped[str] = mapped_column(String(20), index=True)


class DemSample(Base):
    """100 m terrain samples derived from the published DEM and its derivatives."""

    __tablename__ = "dem_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=SRID))
    elevation_m: Mapped[float] = mapped_column(Float)
    slope_deg: Mapped[float] = mapped_column(Float)
    twi: Mapped[float] = mapped_column(Float)
    flow_accumulation: Mapped[float | None] = mapped_column(Float)
    contributing_area_km2: Mapped[float | None] = mapped_column(Float)
    layer_version: Mapped[str] = mapped_column(String(20), index=True)


class PlanningLayer(Base):
    """Tenure/planning overlays. kind ∈ acquisition|layout|setback|corridor|greenbelt."""

    __tablename__ = "planning_layers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geom: Mapped[object] = mapped_column(Geometry(srid=SRID))
    kind: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str | None] = mapped_column(String(40))
    source_doc: Mapped[str | None] = mapped_column(String(200))
    effective_date: Mapped[date | None] = mapped_column(Date)


class LandUseArea(Base):
    """Mapped land use; designation distinguishes reference data from official zoning."""

    __tablename__ = "land_use_areas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))
    source_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    source_class: Mapped[str | None] = mapped_column(String(80))
    source_subtype: Mapped[str | None] = mapped_column(String(80))
    name: Mapped[str | None] = mapped_column(String(240))
    designation: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date)
    layer_version: Mapped[str] = mapped_column(String(20), index=True)


class TerritoryBoundary(Base):
    """Operational clipping boundary; provenance prevents it being treated as cadastral."""

    __tablename__ = "territory_boundaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_version: Mapped[str | None] = mapped_column(String(40))
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StateBoundary(Base):
    """Operational state boundary and readiness summary for nationwide rollout."""

    __tablename__ = "states"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    capital: Mapped[str | None] = mapped_column(String(120))
    centroid_lon: Mapped[float] = mapped_column(Float)
    centroid_lat: Mapped[float] = mapped_column(Float)
    bbox: Mapped[list] = mapped_column(JSONB, default=list)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_version: Mapped[str | None] = mapped_column(String(40))
    readiness: Mapped[str] = mapped_column(String(24), default="setup_required", index=True)
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LgaBoundary(Base):
    """Operational LGA boundary linked to a state."""

    __tablename__ = "lgas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    state_code: Mapped[str] = mapped_column(ForeignKey("states.code"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_version: Mapped[str | None] = mapped_column(String(40))
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MasterplanArea(Base):
    """Official or advisory masterplan polygon normalized to the land-use taxonomy."""

    __tablename__ = "masterplan_areas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    state_code: Mapped[str] = mapped_column(ForeignKey("states.code"), index=True)
    lga_id: Mapped[int | None] = mapped_column(ForeignKey("lgas.id"), index=True)
    plan_name: Mapped[str | None] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(40), index=True)
    source_class: Mapped[str | None] = mapped_column(String(120))
    source_doc: Mapped[str | None] = mapped_column(String(240))
    effective_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    layer_version: Mapped[str] = mapped_column(String(32), index=True)
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StateLayerRegistry(Base):
    """Layer readiness and versioning per state."""

    __tablename__ = "state_layer_registry"

    state_code: Mapped[str] = mapped_column(ForeignKey("states.code"), primary_key=True)
    layer: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), default="unpublished")
    status: Mapped[str] = mapped_column(String(24), default="unpublished", index=True)
    source: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GisUploadBatch(Base):
    """Draft admin upload plus validation and preview payload."""

    __tablename__ = "gis_upload_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    target_layer: Mapped[str] = mapped_column(String(32), index=True)
    state_code: Mapped[str | None] = mapped_column(String(8), index=True)
    file_name: Mapped[str] = mapped_column(String(260))
    file_type: Mapped[str] = mapped_column(String(24))
    source_name: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    license_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    validation_report: Mapped[dict] = mapped_column(JSONB, default=dict)
    attribute_mapping: Mapped[dict] = mapped_column(JSONB, default=dict)
    feature_collection: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminAuditLog(Base):
    """Immutable admin action trail."""

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40), index=True)
    target_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[str | None] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LandCoverRaster(Base):
    """Published wall-to-wall observed cover COG used by point sampling and tiles."""

    __tablename__ = "land_cover_rasters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    raster_path: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    resolution_m: Mapped[int] = mapped_column(Integer)
    classes: Mapped[dict] = mapped_column(JSONB)
    layer_version: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BuildingFootprint(Base):
    """Overture building or preferred building-part geometry for analytical 3D."""

    __tablename__ = "building_footprints"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    parent_source_id: Mapped[str | None] = mapped_column(String(80), index=True)
    feature_type: Mapped[str] = mapped_column(String(24))
    building_class: Mapped[str | None] = mapped_column(String(80))
    height_m: Mapped[float | None] = mapped_column(Float)
    num_floors: Mapped[int | None] = mapped_column(Integer)
    min_height_m: Mapped[float | None] = mapped_column(Float)
    display_height_m: Mapped[float] = mapped_column(Float)
    height_basis: Mapped[str] = mapped_column(String(24), index=True)
    source_datasets: Mapped[list] = mapped_column(JSONB, default=list)
    release: Mapped[str] = mapped_column(String(32))
    layer_version: Mapped[str] = mapped_column(String(32), index=True)
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))


class VegetationCanopyArea(Base):
    """Observed tree-cover patch; geometry is not an individual tree inventory."""

    __tablename__ = "vegetation_canopy_areas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    resolution_m: Mapped[int] = mapped_column(Integer)
    area_ha: Mapped[float] = mapped_column(Float)
    layer_version: Mapped[str] = mapped_column(String(32), index=True)
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=SRID))


class AnalysisRaster(Base):
    """Versioned source catalogue for analysis-ready COGs."""

    __tablename__ = "analysis_rasters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    metric: Mapped[str] = mapped_column(String(48), index=True)
    epoch: Mapped[str | None] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(Text)
    raster_path: Mapped[str] = mapped_column(Text)
    resolution_m: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    licence: Mapped[str | None] = mapped_column(String(160))
    layer_version: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SpatialMetricCell(Base):
    """Query-ready 250 m cells for environmental and development outlook metrics."""

    __tablename__ = "spatial_metric_cells"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cell_id: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    geom: Mapped[object] = mapped_column(Geometry("POLYGON", srid=SRID))
    population_2025: Mapped[float | None] = mapped_column(Float)
    population_2030: Mapped[float | None] = mapped_column(Float)
    population_growth_percentile: Mapped[float | None] = mapped_column(Float)
    built_share_current: Mapped[float | None] = mapped_column(Float)
    built_change_pct: Mapped[float | None] = mapped_column(Float)
    settlement_growth_percentile: Mapped[float | None] = mapped_column(Float)
    green_share: Mapped[float | None] = mapped_column(Float)
    built_bare_share: Mapped[float | None] = mapped_column(Float)
    surface_temp_c: Mapped[float | None] = mapped_column(Float)
    heat_percentile: Mapped[float | None] = mapped_column(Float)
    layer_versions: Mapped[dict] = mapped_column(JSONB, default=dict)
    data_period: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DevelopmentProject(Base):
    """Official public project record with explicit stage and location precision."""

    __tablename__ = "development_projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    official_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300))
    authority: Mapped[str] = mapped_column(String(160))
    agency: Mapped[str | None] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(80), index=True)
    lifecycle_stage: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str | None] = mapped_column(String(120))
    budget_ngn: Mapped[float | None] = mapped_column(Float)
    location_text: Mapped[str] = mapped_column(Text)
    ward: Mapped[str | None] = mapped_column(String(160), index=True)
    area_council: Mapped[str | None] = mapped_column(String(160), index=True)
    geom: Mapped[object | None] = mapped_column(Geometry(srid=SRID))
    location_precision: Mapped[str] = mapped_column(String(32), index=True)
    geocoding_confidence: Mapped[float | None] = mapped_column(Float)
    source_url: Mapped[str] = mapped_column(Text)
    source_published_at: Mapped[date] = mapped_column(Date)
    source_updated_at: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    layer_version: Mapped[str] = mapped_column(String(32), index=True)


class ScoringProfile(Base):
    """Versioned weights & normalisation params per domain (TDD §4.4).

    Weights are configuration, not code, so methodology updates are auditable
    and reproducible. Changes ship as reviewed Alembic migrations.
    """

    __tablename__ = "scoring_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_key: Mapped[str] = mapped_column(String(40), index=True)  # e.g. "fct-v1"
    domain: Mapped[str] = mapped_column(String(20), index=True)
    weights: Mapped[dict] = mapped_column(JSONB)
    normalisation: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[date] = mapped_column(Date, server_default=func.current_date())


class LayerRegistry(Base):
    """Current published version per data layer — the source of truth for the
    `layer_version` discipline (TDD §4.3, §6.1).

    ETL bumps a layer's version on each publish; a Celery sweep then invalidates
    cached `scores` whose `layer_versions` reference an older version. The API
    stamps freshly computed scorecards with the versions read from here.
    """

    __tablename__ = "layer_registry"

    layer: Mapped[str] = mapped_column(String(32), primary_key=True)  # poi|roads|hazard|dem|...
    version: Mapped[str] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Score(Base):
    """Cached scorecards, keyed by location hash + scoring profile + layer versions."""

    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    location_hash: Mapped[str] = mapped_column(String(16), index=True)
    domain: Mapped[str] = mapped_column(String(20), index=True)
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(10))  # High|Medium|Low
    indicators: Mapped[dict] = mapped_column(JSONB, default=dict)
    layer_versions: Mapped[dict] = mapped_column(JSONB, default=dict)
    scoring_profile_id: Mapped[int | None] = mapped_column(ForeignKey("scoring_profiles.id"))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IncidentsAgg(Base):
    """Privacy-preserving district or ward security aggregates."""

    __tablename__ = "incidents_agg"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id"), index=True)
    period: Mapped[str] = mapped_column(String(10))  # e.g. "2026-Q2"
    category: Mapped[str] = mapped_column(String(40))
    count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str | None] = mapped_column(String(80))


class Review(Base):
    """Community reviews. status ∈ pending|published|rejected. Aggregated to district."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geom: Mapped[object | None] = mapped_column(Geometry("POINT", srid=SRID))
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"), index=True)
    rating: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketSample(Base):
    """Geocoded price observations. kind ∈ land|rent|sale."""

    __tablename__ = "market_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=SRID))
    kind: Mapped[str] = mapped_column(String(10), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))
    observed_at: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(120))
    sample_type: Mapped[str] = mapped_column(String(16), default="listing")
    verified: Mapped[bool] = mapped_column(default=False)
    layer_version: Mapped[str] = mapped_column(String(20), default="unpublished", index=True)
    external_id: Mapped[str | None] = mapped_column(String(80), index=True)
    title: Mapped[str | None] = mapped_column(String(240))
    area: Mapped[str | None] = mapped_column(String(80), index=True)
    address: Mapped[str | None] = mapped_column(String(300))
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    property_type: Mapped[str | None] = mapped_column(String(80))
    source_url: Mapped[str | None] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="user")  # user|moderator|admin|enterprise
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiKey(Base):
    """Enterprise keys with tier and quota (TDD §8)."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(20), default="standard")
    quota_daily: Mapped[int] = mapped_column(Integer, default=1000)
    owner: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- Spatial & lookup indexes (GiST on every geom; partial index on poi.category) ---
Index("ix_districts_geom", District.geom, postgresql_using="gist")
Index("ix_wards_geom", Ward.geom, postgresql_using="gist")
Index("ix_locations_geom", Location.geom, postgresql_using="gist")
Index("ix_poi_geom", Poi.geom, postgresql_using="gist")
Index("ix_roads_geom", Road.geom, postgresql_using="gist")
Index("ix_dem_samples_geom", DemSample.geom, postgresql_using="gist")
Index("ix_planning_geom", PlanningLayer.geom, postgresql_using="gist")
Index("ix_land_use_geom", LandUseArea.geom, postgresql_using="gist")
Index("ix_territory_boundaries_geom", TerritoryBoundary.geom, postgresql_using="gist")
Index("ix_states_geom", StateBoundary.geom, postgresql_using="gist")
Index("ix_lgas_geom", LgaBoundary.geom, postgresql_using="gist")
Index("ix_masterplan_areas_geom", MasterplanArea.geom, postgresql_using="gist")
Index("ix_building_footprints_geom", BuildingFootprint.geom, postgresql_using="gist")
Index("ix_vegetation_canopy_areas_geom", VegetationCanopyArea.geom, postgresql_using="gist")
Index("ix_spatial_metric_cells_geom", SpatialMetricCell.geom, postgresql_using="gist")
Index("ix_development_projects_geom", DevelopmentProject.geom, postgresql_using="gist")
Index("ix_reviews_geom", Review.geom, postgresql_using="gist")
Index("ix_market_geom", MarketSample.geom, postgresql_using="gist")

"""ETL configuration (shares the root .env with the API)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ETLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # PostGIS
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "propinsight"
    postgres_user: str = "aia"
    postgres_password: str = "aia"
    database_url: str | None = None

    # Redis (Celery broker + result backend + cache the API reads)
    redis_url: str = "redis://redis:6379/0"

    # GGIS Flood Watch (hazard tile mirror harvest)
    ggis_flood_base_url: str = "http://mock-ggis:9100"
    ggis_flood_api_key: str = "dev-key"
    ggis_flood_hmac_secret: str = "dev-secret"

    # Google Earth Engine (DEM + remote-sensing analysis, Overview §6.3).
    # Service-account auth. The key may be a path to the JSON key file or the
    # JSON content itself. Project is parsed from the SA email when unset.
    gee_service_account_email: str | None = None
    gee_service_account_key: str | None = None
    gee_project: str | None = None
    # Earth Engine is primary for non-flood environmental analysis. ``direct``
    # retains the download pipeline as an explicit operational fallback.
    environment_source: str = "gee"

    # POI sources to ingest (comma-separated): overpass | overture | grid3 | ...
    poi_sources: str = "overpass,overture,grid3"
    # Overture Maps release (GeoParquet). Bump to the latest release periodically.
    overture_release: str = "2026-07-22.0"
    # GRID3 Nigeria ArcGIS FeatureServer layer URLs (health / education). Non-OSM.
    grid3_health_url: str = (
        "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/"
        "GRID3_NGA_health_facilities_v2_0/FeatureServer/0"
    )
    grid3_education_url: str = (
        "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/"
        "Schools_in_Nigeria/FeatureServer/0"
    )
    grid3_wards_url: str = (
        "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/"
        "GRID3_NGA_operational_wards_v3_0/FeatureServer/0"
    )

    # Wall-to-wall observed cover. ``auto`` prefers Dynamic World and falls
    # back to the open ESA WorldCover COGs when Earth Engine IAM is unavailable.
    land_cover_source: str = "auto"
    land_cover_scale_m: int = 30

    # Direct authoritative raster fallback sources.
    copernicus_stac_url: str = "https://stac.dataspace.copernicus.eu/v1"
    copernicus_dem_collection: str = "cop-dem-glo-30-dged-cog"
    # Planetary Computer exposes the authoritative USGS Collection 2 archive
    # through publicly signed COG URLs; LandsatLook now redirects to login.
    usgs_landsat_stac_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    usgs_landsat_st_collection: str = "landsat-c2-l2"
    planetary_computer_sign_url: str = (
        "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
    )
    worldpop_2025_url: str | None = (
        "https://data.worldpop.org/repo/wopr/NGA/population/v3.0/"
        "NGA_population_v3_0_gridded.zip"
    )
    # Official GHSL Mollweide 100 m tile R8_C19 covers the full FCT AOI.
    ghsl_population_2025_url: str | None = (
        "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        "GHS_POP_GLOBE_R2023A/GHS_POP_E2025_GLOBE_R2023A_54009_100/"
        "V1-0/tiles/GHS_POP_E2025_GLOBE_R2023A_54009_100_V1_0_R8_C19.zip"
    )
    ghsl_population_2030_url: str | None = (
        "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        "GHS_POP_GLOBE_R2023A/GHS_POP_E2030_GLOBE_R2023A_54009_100/"
        "V1-0/tiles/GHS_POP_E2030_GLOBE_R2023A_54009_100_V1_0_R8_C19.zip"
    )
    ghsl_built_current_url: str | None = (
        "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        "GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2025_GLOBE_R2023A_54009_100/"
        "V1-0/tiles/GHS_BUILT_S_E2025_GLOBE_R2023A_54009_100_V1_0_R8_C19.zip"
    )
    ghsl_built_2030_url: str | None = (
        "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        "GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2030_GLOBE_R2023A_54009_100/"
        "V1-0/tiles/GHS_BUILT_S_E2030_GLOBE_R2023A_54009_100_V1_0_R8_C19.zip"
    )
    official_projects_feed_urls: str = ""

    # Licensed open market fallback used when no partner CSV is mounted.
    market_source_url: str = (
        "https://huggingface.co/datasets/ayookuns/abuja-housing-prices-v1/"
        "resolve/main/groundwork_abuja_housing_v1.csv"
    )

    # Data working directory (COGs, extracts) — mounted volume in compose.
    data_dir: str = "/data"

    # Area of interest for the pilot.
    aoi_name: str = "FCT"
    # Geofabrik extract for OSM (Nigeria); clipped to the AOI in the pipeline.
    osm_extract_url: str = "https://download.geofabrik.de/africa/nigeria-latest.osm.pbf"

    @property
    def poi_sources_list(self) -> list[str]:
        return [s.strip() for s in self.poi_sources.split(",") if s.strip()]

    @property
    def official_projects_feeds(self) -> list[str]:
        return [s.strip() for s in self.official_projects_feed_urls.split(",") if s.strip()]

    @property
    def sync_sqlalchemy_url(self) -> str:
        """Synchronous URL (psycopg3) — ETL uses sync engines inside Celery tasks."""
        if self.database_url:
            # Normalise an async URL to sync if the shared value carries a driver.
            return self.database_url.replace("+asyncpg", "+psycopg")
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> ETLSettings:
    return ETLSettings()

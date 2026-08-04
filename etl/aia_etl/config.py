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

    # POI sources to ingest (comma-separated): overpass | overture | ...
    poi_sources: str = "overpass"
    # Overture Maps release (GeoParquet). Bump to the latest release periodically.
    overture_release: str = "2024-11-13.0"

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

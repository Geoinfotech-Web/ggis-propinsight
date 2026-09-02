"""Application configuration, loaded from environment (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        # Repo-root `.env` (docker-compose) and local `services/api/.env`.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
    )

    # App
    aia_env: str = "dev"
    aia_log_level: str = "INFO"

    # PostGIS
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "propinsight"
    postgres_user: str = "aia"
    postgres_password: str = "aia"
    database_url: str | None = None

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # GGIS Flood Watch integration (TDD §5)
    ggis_flood_base_url: str = "http://mock-ggis:9100"
    ggis_flood_api_key: str = "dev-key"
    ggis_flood_hmac_secret: str = "dev-secret"
    ggis_flood_timeout_ms: int = 5_000
    ggis_flood_data_mode: Literal["mock", "live"] = "mock"
    enext_coverage_base_url: str = "https://server.enextwireless.com:8443/geoserver"
    enext_coverage_timeout_ms: int = 4_000

    # Auth
    jwt_secret: str = "change-me-dev-only"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 30
    aia_admin_email: str | None = None
    aia_admin_password: str | None = None
    aia_admin_password_hash: str | None = None

    # CORS
    cors_origins: str = "http://localhost:5173"

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

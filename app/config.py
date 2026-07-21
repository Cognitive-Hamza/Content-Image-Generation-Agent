from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Runtime environment ─────────────────────────────────────────────────
    ENV: Literal["dev", "staging", "prod"] = "dev"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+psycopg2://cig:cig@localhost:5432/cig"

    # ── Auth (mechanism owned by SysOps — abstraction only) ─────────────────
    AUTH_MODE: Literal["header", "jwt", "dev"] = "dev"
    AUTH_HEADER_NAME: str = "X-Auth-Request-Email"
    AUTH_JWT_SECRET: str | None = None
    AUTH_JWT_JWKS_URL: str | None = None
    AUTH_JWT_EMAIL_CLAIM: str = "email"
    DEV_USER_EMAIL: str | None = None

    # ── Session (flash messages only, not general state) ────────────────────
    SESSION_SECRET_KEY: str = "dev-insecure-change-me"

    # ── Storage backend (vendor owned by SysOps — abstraction only) ─────────
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_ROOT: str = "./data/storage"
    S3_BUCKET: str | None = None
    S3_REGION: str | None = None
    S3_ENDPOINT_URL: str | None = None  # set for MinIO / any S3-compatible dev target

    # ── Content/image generation API keys (unchanged from the Streamlit app) ─
    ANTHROPIC_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # ── One-off SQLite -> Postgres migration (scripts/migrate_sqlite_to_postgres.py) ─
    ALNAFI_DB_PATH: str = "./data/alnafi_pipeline.db"
    MIGRATION_FALLBACK_USER_EMAIL: str = "migration@alnafi.local"


@lru_cache
def get_settings() -> Settings:
    return Settings()

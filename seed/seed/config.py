"""Configuration loaded from environment variables / .env."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    sf_username: str
    sf_password: str
    sf_security_token: str
    sf_domain: str = "login"
    sf_consumer_key: str | None = None
    sf_consumer_secret: str | None = None

    stripe_secret_key: str

    hubspot_access_token: str
    hubspot_portal_id: str

    gcp_project_id: str = "truthkeeper-hack-2026"
    bq_dataset: str = "truthkeeper_demo"

    seed_base_date: date

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    return Settings()

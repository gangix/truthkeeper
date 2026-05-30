"""Configuration loaded from environment variables / .env."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    sf_username: str
    sf_password: str = ""
    sf_security_token: str = ""
    sf_domain: str = "login"
    sf_consumer_key: str | None = None
    sf_consumer_secret: str | None = None
    # Override for orgs that require My Domain for OAuth (newer Agentforce orgs).
    # Example: "orgfarm-abc123.develop.my.salesforce.com" (no scheme, no path).
    sf_login_host: str | None = None
    # JWT Bearer flow (preferred for Agentforce / newer DE orgs where the
    # username-password OAuth flow is blocked at the Connected App level).
    # Use this with an External Client App that has Digital Signatures
    # enabled and the cert uploaded.
    sf_jwt_consumer_key: str | None = None
    # One of these must be set when sf_jwt_consumer_key is set:
    #   sf_jwt_private_key: full PEM contents (with newlines) — for Cloud Run
    #     prefer the _b64 form, which is decoded before use.
    #   sf_jwt_private_key_b64: base64-encoded PEM (single line, env-var safe).
    #   sf_jwt_private_key_path: filesystem path to the PEM file.
    sf_jwt_private_key: str | None = None
    sf_jwt_private_key_b64: str | None = None
    sf_jwt_private_key_path: str | None = None

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

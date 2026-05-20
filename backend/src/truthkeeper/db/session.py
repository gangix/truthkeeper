"""Async SQLAlchemy engine + session factory + FastAPI dependency."""

from __future__ import annotations

import os
import ssl
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _database_url() -> tuple[str, dict]:
    """Return (url_without_unsupported_params, connect_args) for asyncpg.

    asyncpg does not accept ``sslmode`` or ``channel_binding`` as query params.
    We strip them from the URL and instead pass ``ssl=<SSLContext>`` via
    connect_args when SSL is required.
    """
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not set. Add the Neon connection string to "
            "validation/.env (local) or Cloud Run env (prod). "
            "Format: postgresql+asyncpg://user:pass@host/dbname"
        )
    # Neon copy-paste defaults are "postgresql://..."; SQLAlchemy needs the driver suffix.
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]

    parsed = urlparse(raw)
    params = parse_qs(parsed.query, keep_blank_values=True)

    # Extract params that asyncpg can't handle as URL query parameters
    sslmode = params.pop("sslmode", ["disable"])[0]
    params.pop("channel_binding", None)  # not supported by asyncpg at all

    new_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))

    connect_args: dict = {}
    if sslmode in ("require", "verify-ca", "verify-full"):
        ctx = ssl.create_default_context()
        if sslmode == "require":
            # Neon: trust the server cert (matches psycopg2 sslmode=require semantics)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx

    return clean_url, connect_args


_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        url, connect_args = _database_url()
        _engine = create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    if _sessionmaker is None:
        raise RuntimeError("_sessionmaker not initialised; call get_engine() first")
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession scoped to one request."""
    async with get_sessionmaker()() as session:
        yield session

"""Async SQLAlchemy engine + session factory + FastAPI dependency."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _database_url() -> str:
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
    return raw


_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(_database_url(), pool_pre_ping=True)
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

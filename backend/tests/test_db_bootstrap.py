"""Bootstrap idempotency: running init_db twice leaves exactly one DEMO_SPEC row."""

import os

import pytest
from sqlalchemy import func, select


def _has_database_url() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@pytest.mark.skipif(not _has_database_url(), reason="DATABASE_URL not configured")
@pytest.mark.asyncio
async def test_init_db_is_idempotent() -> None:
    from truthkeeper.db.bootstrap import init_db
    from truthkeeper.db.models import Spec
    from truthkeeper.db.session import get_sessionmaker
    from truthkeeper.spec.demo import DEMO_SPEC

    await init_db()
    await init_db()

    async with get_sessionmaker()() as session:
        result = await session.execute(
            select(func.count()).select_from(Spec).where(
                Spec.company_id == DEMO_SPEC.company_id
            )
        )
        count = result.scalar_one()
    assert count == 1

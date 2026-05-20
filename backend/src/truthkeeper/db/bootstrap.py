"""DB initialization: CREATE TABLE on startup + seed DEMO_SPEC if specs is empty."""

from __future__ import annotations

import logging

from sqlalchemy import select

from truthkeeper.db.models import Base, Company, Spec
from truthkeeper.db.session import get_engine, get_sessionmaker
from truthkeeper.spec.demo import DEMO_SPEC

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Create tables and seed DEMO_SPEC if the specs table is empty.

    Idempotent: safe to call on every startup.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_sessionmaker()() as session:
        existing = (
            await session.execute(select(Spec).where(Spec.company_id == DEMO_SPEC.company_id))
        ).scalar_one_or_none()
        if existing is not None:
            logger.info("init_db: spec for %s already present, skipping seed", DEMO_SPEC.company_id)
            return

        company = (
            await session.execute(select(Company).where(Company.id == DEMO_SPEC.company_id))
        ).scalar_one_or_none()
        if company is None:
            session.add(Company(id=DEMO_SPEC.company_id, name=DEMO_SPEC.company_name))

        session.add(
            Spec(
                company_id=DEMO_SPEC.company_id,
                spec_json=DEMO_SPEC.model_dump(mode="json"),
                version=1,
                agent_run_id=None,
            )
        )
        await session.commit()
        logger.info("init_db: seeded DEMO_SPEC for %s", DEMO_SPEC.company_id)

"""Smoke check: ORM mappings load without import errors and have expected columns."""

from truthkeeper.db.models import Base, Company, Spec


def test_metadata_has_two_tables() -> None:
    assert {"companies", "specs"} <= set(Base.metadata.tables.keys())


def test_company_columns() -> None:
    cols = {c.name for c in Company.__table__.columns}
    assert {"id", "name", "created_at"} == cols


def test_spec_columns() -> None:
    cols = {c.name for c in Spec.__table__.columns}
    assert {"company_id", "spec_json", "version", "approved_at", "agent_run_id"} == cols

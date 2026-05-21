"""ORM shape smoke test for the Approval model."""

from truthkeeper.db.models import Approval, Base


def test_approval_table_registered() -> None:
    assert "approvals" in Base.metadata.tables


def test_approval_columns() -> None:
    cols = {c.name for c in Approval.__table__.columns}
    expected = {
        "id",
        "company_id",
        "rule_id",
        "violation_id",
        "action_idx",
        "target_system",
        "action_type",
        "parameters_json",
        "status",
        "external_id",
        "message",
        "error",
        "executed_at",
    }
    assert cols == expected

"""Approve endpoint contract: dispatch routing, cache miss, idx range, unsupported."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from truthkeeper.spec.models import (
    CorrectiveActionTemplate,
    Rule,
    Severity,
    SystemName,
)


@pytest.fixture(autouse=True)
def clear_overrides():
    from truthkeeper.main import app
    yield
    app.dependency_overrides.clear()


def _make_session_mock_with_executed_rows(rows=None):
    """Build a session mock with controllable execute().scalars().all()."""
    session = AsyncMock()
    result_obj = MagicMock()
    if rows is None:
        result_obj.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
    else:
        result_obj.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=rows))
        )
    session.execute = AsyncMock(return_value=result_obj)
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _stub_rule() -> Rule:
    return Rule(
        id="D1",
        name="active sub for churned account",
        description="...",
        severity=Severity.critical,
        sql="SELECT 1",
        reasoning_template="rt",
        corrective_action_templates=[
            CorrectiveActionTemplate(
                target_system=SystemName.stripe,
                action_type="cancel_subscription",
                parameter_mapping={"subscription_id": "stripe_subscription_id"},
                description="cancel sub",
            )
        ],
        monetary_impact_formula=None,
    )


def test_approve_404_on_cache_miss() -> None:
    from truthkeeper.db.session import get_session
    from truthkeeper.main import app

    async def _override():
        yield _make_session_mock_with_executed_rows()

    app.dependency_overrides[get_session] = _override

    client = TestClient(app)
    response = client.post(
        "/companies/truthkeeper-demo/disagreements/no-such-vid/actions/0/approve"
    )
    assert response.status_code == 404


def test_approve_400_on_action_idx_out_of_range(monkeypatch) -> None:
    from truthkeeper.db.session import get_session
    from truthkeeper.main import app
    import truthkeeper.reasoning.orchestrator as orch

    rule = _stub_rule()
    row = {"stripe_subscription_id": "sub_x"}
    monkeypatch.setitem(orch._DISAGREEMENTS_CACHE, "vid1", (rule, row, MagicMock()))

    async def _override():
        yield _make_session_mock_with_executed_rows()

    app.dependency_overrides[get_session] = _override

    client = TestClient(app)
    response = client.post(
        "/companies/truthkeeper-demo/disagreements/vid1/actions/99/approve"
    )
    assert response.status_code == 400


def test_approve_succeeds_and_persists(monkeypatch) -> None:
    from truthkeeper.actions import ExecutionResult
    from truthkeeper.db.session import get_session
    from truthkeeper.main import app
    import truthkeeper.api.approvals as approvals_mod
    import truthkeeper.reasoning.orchestrator as orch

    rule = _stub_rule()
    row = {"stripe_subscription_id": "sub_x"}
    monkeypatch.setitem(orch._DISAGREEMENTS_CACHE, "vid2", (rule, row, MagicMock()))

    async def fake_dispatch(system, action_type, parameters):
        return ExecutionResult(
            status="succeeded",
            external_id="sub_x",
            message="Stripe subscription sub_x cancelled",
        )

    monkeypatch.setattr(approvals_mod, "dispatch_action", fake_dispatch)

    session_mock = _make_session_mock_with_executed_rows()

    async def _override():
        yield session_mock

    app.dependency_overrides[get_session] = _override

    client = TestClient(app)
    response = client.post(
        "/companies/truthkeeper-demo/disagreements/vid2/actions/0/approve"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_result"]["status"] == "succeeded"
    assert body["execution_result"]["external_id"] == "sub_x"
    assert isinstance(body["approval_id"], str)
    session_mock.add.assert_called_once()
    session_mock.commit.assert_awaited_once()


def test_approve_persists_failed_when_dispatch_returns_failed(monkeypatch) -> None:
    from truthkeeper.actions import ExecutionResult
    from truthkeeper.db.session import get_session
    from truthkeeper.main import app
    import truthkeeper.api.approvals as approvals_mod
    import truthkeeper.reasoning.orchestrator as orch

    rule = _stub_rule()
    row = {"stripe_subscription_id": "sub_x"}
    monkeypatch.setitem(orch._DISAGREEMENTS_CACHE, "vid3", (rule, row, MagicMock()))

    async def fake_dispatch(system, action_type, parameters):
        return ExecutionResult(
            status="failed",
            error="stripe.error.InvalidRequestError: No such subscription",
        )

    monkeypatch.setattr(approvals_mod, "dispatch_action", fake_dispatch)

    session_mock = _make_session_mock_with_executed_rows()

    async def _override():
        yield session_mock

    app.dependency_overrides[get_session] = _override

    client = TestClient(app)
    response = client.post(
        "/companies/truthkeeper-demo/disagreements/vid3/actions/0/approve"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_result"]["status"] == "failed"
    session_mock.add.assert_called_once()
    session_mock.commit.assert_awaited_once()


def test_approve_501_on_unsupported_action(monkeypatch) -> None:
    from truthkeeper.actions import UnsupportedActionError
    from truthkeeper.db.session import get_session
    from truthkeeper.main import app
    import truthkeeper.api.approvals as approvals_mod
    import truthkeeper.reasoning.orchestrator as orch

    rule = _stub_rule()
    row = {"stripe_subscription_id": "sub_x"}
    monkeypatch.setitem(orch._DISAGREEMENTS_CACHE, "vid4", (rule, row, MagicMock()))

    async def fake_dispatch(system, action_type, parameters):
        raise UnsupportedActionError("not implemented in this build")

    monkeypatch.setattr(approvals_mod, "dispatch_action", fake_dispatch)

    session_mock = _make_session_mock_with_executed_rows()

    async def _override():
        yield session_mock

    app.dependency_overrides[get_session] = _override

    client = TestClient(app)
    response = client.post(
        "/companies/truthkeeper-demo/disagreements/vid4/actions/0/approve"
    )
    assert response.status_code == 501
    session_mock.add.assert_called_once()  # failed-approval row still persisted

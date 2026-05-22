from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from truthkeeper.api import companies as companies_module
from truthkeeper.db.models import Spec
from truthkeeper.db.session import get_session
from truthkeeper.main import app
from truthkeeper.reasoning.output import (
    DraftedAction,
    ReasoningOutput,
    ReconciliationReport,
    RuleReconciliation,
    ViolationReasoning,
)
from truthkeeper.spec.demo import DEMO_SPEC
from truthkeeper.spec.models import Severity, SystemName


def _make_mock_session(company_id: str | None) -> AsyncGenerator:
    """Return an async context-manager-like session stub.

    If company_id is provided the session returns a Spec row for that company;
    otherwise it returns None (simulating an unknown company).
    """

    async def _get_session_override() -> AsyncGenerator:
        mock_session = AsyncMock()

        if company_id is not None:
            spec_row = MagicMock(spec=Spec)
            spec_row.company_id = DEMO_SPEC.company_id
            spec_row.spec_json = DEMO_SPEC.model_dump(mode="json")

            result = MagicMock()
            result.scalar_one_or_none.return_value = spec_row
        else:
            result = MagicMock()
            result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=result)
        yield mock_session

    return _get_session_override


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Ensure overrides are cleaned up after each test."""
    yield
    app.dependency_overrides.clear()


def test_get_spec_returns_demo_company() -> None:
    app.dependency_overrides[get_session] = _make_mock_session("truthkeeper-demo")
    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/companies/truthkeeper-demo/spec")
    assert response.status_code == 200
    payload = response.json()
    assert payload["company_id"] == "truthkeeper-demo"
    assert payload["company_name"] == "TruthKeeper Demo Co"
    assert {r["id"] for r in payload["rules"]} == {"D1", "D2", "D3", "D4", "D5"}
    assert len(payload["connected_systems"]) == 3


def test_get_spec_404_for_unknown_company() -> None:
    app.dependency_overrides[get_session] = _make_mock_session(None)
    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/companies/does-not-exist/spec")
    assert response.status_code == 404
    assert "does-not-exist" in response.json()["detail"]


def test_reconcile_endpoint_calls_orchestrator_with_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """The endpoint must forward path + query + body args to reconcile_all_rules."""

    app.dependency_overrides[get_session] = _make_mock_session("truthkeeper-demo")
    client = TestClient(app, raise_server_exceptions=True)

    captured: dict[str, object] = {}

    async def stub_reconcile_all_rules(
        spec, *, max_violations_per_rule, rule_ids=None
    ) -> ReconciliationReport:
        captured["spec_company_id"] = spec.company_id
        captured["max_violations_per_rule"] = max_violations_per_rule
        captured["rule_ids"] = list(rule_ids) if rule_ids is not None else None
        return ReconciliationReport(
            company_id=spec.company_id,
            company_name=spec.company_name,
            rules=[
                RuleReconciliation(
                    rule_id="D1",
                    rule_name="stub",
                    severity=Severity.critical,
                    violation_count=1,
                    sampled_count=1,
                    violations=[
                        ViolationReasoning(
                            violation_id="test-vid",
                            violation={"k": "v"},
                            reasoning=ReasoningOutput(
                                explanation="stubbed",
                                likely_cause="stubbed",
                                drafted_actions=[
                                    DraftedAction(
                                        target_system=SystemName.stripe,
                                        action_type="noop",
                                        parameters={},
                                        description="stub",
                                    )
                                ],
                            ),
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(
        companies_module, "reconcile_all_rules", stub_reconcile_all_rules
    )

    response = client.post(
        "/companies/truthkeeper-demo/reconcile?max_violations_per_rule=1",
        json={"rule_ids": ["D1"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["company_id"] == "truthkeeper-demo"
    assert payload["rules"][0]["rule_id"] == "D1"
    assert payload["rules"][0]["violations"][0]["reasoning"]["explanation"] == "stubbed"

    assert captured["spec_company_id"] == "truthkeeper-demo"
    assert captured["max_violations_per_rule"] == 1
    assert captured["rule_ids"] == ["D1"]


def test_reconcile_endpoint_accepts_empty_body(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_session] = _make_mock_session("truthkeeper-demo")
    client = TestClient(app, raise_server_exceptions=True)

    async def stub(spec, *, max_violations_per_rule, rule_ids=None) -> ReconciliationReport:
        return ReconciliationReport(
            company_id=spec.company_id,
            company_name=spec.company_name,
            rules=[],
        )

    monkeypatch.setattr(companies_module, "reconcile_all_rules", stub)

    response = client.post("/companies/truthkeeper-demo/reconcile")
    assert response.status_code == 200
    assert response.json()["rules"] == []


def test_reconcile_endpoint_404_for_unknown_company() -> None:
    app.dependency_overrides[get_session] = _make_mock_session(None)
    client = TestClient(app, raise_server_exceptions=True)
    response = client.post("/companies/does-not-exist/reconcile")
    assert response.status_code == 404

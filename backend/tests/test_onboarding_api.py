"""Smoke test the approve endpoint with a stubbed cached proposal."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Cleans up FastAPI dependency overrides between tests."""
    from truthkeeper.main import app

    yield
    app.dependency_overrides.clear()


def _make_mock_session_for_approve():
    """Build a session mock that lets approve_onboarding pass without a real DB."""
    session = AsyncMock()
    # All execute() returns scalar_one_or_none() = None (no existing rows).
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def test_approve_404_when_proposal_missing() -> None:
    from truthkeeper.main import app
    from truthkeeper.db.session import get_session

    async def _override():
        yield _make_mock_session_for_approve()

    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    response = client.post(
        "/companies/truthkeeper-demo/onboard/approve",
        json={
            "proposal_id": "does-not-exist",
            "company_name": "Foo",
            "accepted_entity_ids": ["ent-1"],
            "accepted_rule_ids": ["rule-1"],
            "accepted_vocab_ids": [],
        },
    )
    assert response.status_code == 404


def test_approve_400_when_no_rules_selected() -> None:
    from truthkeeper.main import app
    from truthkeeper.db.session import get_session
    from truthkeeper.onboarding import pipeline
    from truthkeeper.onboarding.proposal import (
        OnboardingProposal,
        ProposedEntity,
        ProposedEntityMapping,
    )
    from truthkeeper.spec.models import SystemName

    proposal = OnboardingProposal(
        proposal_id="test-prop-1",
        entities=[
            ProposedEntity(
                proposal_id="ent-1",
                name="Customer",
                mappings=[
                    ProposedEntityMapping(
                        system=SystemName.salesforce, table="account", id_field="id"
                    )
                ],
            )
        ],
        rules=[],
        vocabulary=[],
        source_run_id="run-1",
    )
    pipeline._PROPOSAL_CACHE[proposal.proposal_id] = proposal

    async def _override():
        yield _make_mock_session_for_approve()

    app.dependency_overrides[get_session] = _override

    client = TestClient(app)
    response = client.post(
        "/companies/truthkeeper-demo/onboard/approve",
        json={
            "proposal_id": "test-prop-1",
            "company_name": "Foo",
            "accepted_entity_ids": ["ent-1"],
            "accepted_rule_ids": [],
            "accepted_vocab_ids": [],
        },
    )
    assert response.status_code == 400

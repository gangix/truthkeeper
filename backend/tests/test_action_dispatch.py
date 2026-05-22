"""Dispatch table contract: registered pairs route, unsupported pairs raise."""

import pytest

from truthkeeper.actions import ExecutionResult, UnsupportedActionError, dispatch_action
from truthkeeper.spec.models import SystemName


@pytest.mark.asyncio
async def test_stripe_cancel_subscription_routes_to_executor(monkeypatch) -> None:
    captured = {}

    async def fake(parameters):
        captured["params"] = parameters
        return ExecutionResult(status="succeeded", external_id="sub_x", message="ok")

    monkeypatch.setattr("truthkeeper.actions.dispatch.cancel_subscription", fake)
    # Patch the lookup-table entry too (the dict was built at import time).
    import truthkeeper.actions.dispatch as d

    d._DISPATCH[(SystemName.stripe, "cancel_subscription")] = fake

    result = await dispatch_action(
        SystemName.stripe, "cancel_subscription", {"subscription_id": "sub_x"}
    )
    assert result.status == "succeeded"
    assert result.external_id == "sub_x"
    assert captured["params"] == {"subscription_id": "sub_x"}


@pytest.mark.asyncio
async def test_salesforce_update_account_status_registered() -> None:
    import truthkeeper.actions.dispatch as d

    assert (SystemName.salesforce, "update_account_status") in d._DISPATCH


@pytest.mark.asyncio
async def test_hubspot_remove_from_sequence_registered() -> None:
    import truthkeeper.actions.dispatch as d

    assert (SystemName.hubspot, "remove_from_sequence") in d._DISPATCH


@pytest.mark.asyncio
async def test_unsupported_d2_action_raises() -> None:
    with pytest.raises(UnsupportedActionError) as exc_info:
        await dispatch_action(
            SystemName.salesforce, "reassign_owner_to_csm", {}
        )
    assert "reassign_owner_to_csm" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cross_system_unsupported_raises() -> None:
    with pytest.raises(UnsupportedActionError):
        # cancel_subscription is a Stripe action, not Salesforce.
        await dispatch_action(SystemName.salesforce, "cancel_subscription", {})

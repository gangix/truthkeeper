"""Lookup table from (system, action_type) → executor function.

Unsupported pairs raise UnsupportedActionError; the approve endpoint
converts that to 501. Persisted failed-approval row is added by the
endpoint regardless, so the audit captures the attempt.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from truthkeeper.actions.hubspot import remove_from_sequence
from truthkeeper.actions.result import ExecutionResult
from truthkeeper.actions.salesforce import update_account_status
from truthkeeper.actions.stripe import cancel_subscription
from truthkeeper.spec.models import SystemName

ExecutorFn = Callable[[dict[str, str]], Awaitable[ExecutionResult]]


class UnsupportedActionError(Exception):
    """No executor registered for the given (system, action_type) pair."""


_DISPATCH: dict[tuple[SystemName, str], ExecutorFn] = {
    (SystemName.stripe, "cancel_subscription"): cancel_subscription,
    (SystemName.salesforce, "update_account_status"): update_account_status,
    (SystemName.hubspot, "remove_from_sequence"): remove_from_sequence,
}


async def dispatch_action(
    target_system: SystemName,
    action_type: str,
    parameters: dict[str, str],
) -> ExecutionResult:
    """Look up an executor and run it.

    Raises UnsupportedActionError if no executor is registered for the pair.
    Otherwise delegates to the executor (which itself never raises — it
    returns an ExecutionResult with status='failed' on errors).
    """
    fn = _DISPATCH.get((target_system, action_type))
    if fn is None:
        raise UnsupportedActionError(
            f"No executor registered for {target_system.value}.{action_type}"
        )
    return await fn(parameters)

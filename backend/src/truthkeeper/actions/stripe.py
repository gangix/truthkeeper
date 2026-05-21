"""Stripe action executor: cancel_subscription."""

from __future__ import annotations

import asyncio
import logging
import os

import stripe as stripe_sdk

from truthkeeper.actions.result import ExecutionResult

logger = logging.getLogger(__name__)


def _client() -> None:
    """Configure the stripe SDK from env. Raises if STRIPE_SECRET_KEY missing."""
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY not set. Add to validation/.env (local) or "
            "Cloud Run env vars (prod)."
        )
    stripe_sdk.api_key = key


async def cancel_subscription(parameters: dict[str, str]) -> ExecutionResult:
    """Cancel a Stripe subscription by its id.

    `parameters["subscription_id"]` is the Stripe subscription id resolved
    from the violation row via the rule's parameter_mapping (e.g.
    "sub_1AbC2D").
    """
    subscription_id = parameters.get("subscription_id")
    if not subscription_id:
        return ExecutionResult(
            status="failed",
            error="parameter 'subscription_id' missing or empty",
        )

    try:
        _client()
    except RuntimeError as exc:
        return ExecutionResult(status="failed", error=str(exc))

    try:
        # stripe SDK is sync; run in a thread to keep the event loop unblocked.
        sub = await asyncio.wait_for(
            asyncio.to_thread(stripe_sdk.Subscription.delete, subscription_id),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        return ExecutionResult(
            status="failed",
            error=f"Stripe API timeout (>20s) cancelling {subscription_id}",
        )
    except Exception as exc:  # noqa: BLE001 — Stripe SDK raises many subclasses
        logger.warning("Stripe cancel_subscription failed for %s: %s",
                       subscription_id, exc)
        return ExecutionResult(
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )

    canceled_id = getattr(sub, "id", subscription_id)
    return ExecutionResult(
        status="succeeded",
        external_id=canceled_id,
        message=f"Stripe subscription {canceled_id} cancelled",
    )

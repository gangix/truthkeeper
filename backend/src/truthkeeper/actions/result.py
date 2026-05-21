"""Shared result shape returned by every executor function."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ExecutionResult(BaseModel):
    """Outcome of one approve-click → SaaS API call.

    `external_id` is the system's own identifier for the resource we acted on
    (e.g. Stripe subscription id, Salesforce account id), so the audit row can
    cross-reference back to the SaaS system.

    `message` is the human-readable summary shown in the UI on success
    (e.g. "Stripe subscription sub_1AbC2D cancelled").

    `error` is populated only when `status == "failed"`.
    """

    status: Literal["succeeded", "failed"]
    external_id: str | None = None
    message: str = ""
    error: str | None = None

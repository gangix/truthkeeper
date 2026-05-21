"""Salesforce action executor: update_account_status.

Uses simple-salesforce. Authenticates via OAuth Username-Password flow
(matches the existing seed/Salesforce_client pattern).

Status-field name handling: the rule's parameter_mapping uses "new_status"
to provide the target value. The SF field name itself (`Status__c` custom
field vs the built-in Status) is probed at first call and cached for the
session.
"""

from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache

from simple_salesforce import Salesforce

from truthkeeper.actions.result import ExecutionResult

logger = logging.getLogger(__name__)

_STATUS_FIELD_CANDIDATES = ("Status__c", "Status", "Account_Status__c")


def _required_env() -> dict[str, str]:
    keys = (
        "SF_USERNAME",
        "SF_PASSWORD",
        "SF_SECURITY_TOKEN",
        "SF_CONSUMER_KEY",
        "SF_CONSUMER_SECRET",
    )
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Salesforce credentials missing: {', '.join(missing)}. "
            "Add to validation/.env (local) or Cloud Run env (prod)."
        )
    return {k: os.environ[k] for k in keys}


@lru_cache(maxsize=1)
def _client() -> Salesforce:
    env = _required_env()
    return Salesforce(
        username=env["SF_USERNAME"],
        password=env["SF_PASSWORD"],
        security_token=env["SF_SECURITY_TOKEN"],
        consumer_key=env["SF_CONSUMER_KEY"],
        consumer_secret=env["SF_CONSUMER_SECRET"],
    )


@lru_cache(maxsize=1)
def _account_status_field() -> str:
    """Probe which Account field carries the status value.

    Salesforce orgs vary: some use the built-in Account.Status, others use
    a custom Status__c field. We introspect the Account describe() once and
    cache the result.
    """
    sf = _client()
    fields = {f["name"] for f in sf.Account.describe()["fields"]}
    for candidate in _STATUS_FIELD_CANDIDATES:
        if candidate in fields:
            return candidate
    raise RuntimeError(
        "No Account status field found. Tried: "
        + ", ".join(_STATUS_FIELD_CANDIDATES)
    )


async def update_account_status(parameters: dict[str, str]) -> ExecutionResult:
    """Update a Salesforce Account's status field.

    `parameters["account_id"]` — the Salesforce Account id (e.g. "001AbCdEf...")
    `parameters["new_status"]` — the new status string (e.g. "Churned")
    """
    account_id = parameters.get("account_id")
    new_status = parameters.get("new_status")
    if not account_id or not new_status:
        return ExecutionResult(
            status="failed",
            error=(
                "parameters must include 'account_id' and 'new_status'; got "
                f"account_id={account_id!r} new_status={new_status!r}"
            ),
        )

    try:
        sf = _client()
        field = _account_status_field()
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult(status="failed", error=f"{type(exc).__name__}: {exc}")

    try:
        await asyncio.wait_for(
            asyncio.to_thread(sf.Account.update, account_id, {field: new_status}),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        return ExecutionResult(
            status="failed",
            error=f"Salesforce API timeout (>20s) updating {account_id}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Salesforce update_account_status failed for %s: %s", account_id, exc
        )
        return ExecutionResult(
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )

    return ExecutionResult(
        status="succeeded",
        external_id=account_id,
        message=f"Salesforce Account {account_id} status set to {new_status} (field {field})",
    )

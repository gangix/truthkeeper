"""Salesforce action executor: update_account_status.

Auth: OAuth 2.0 JWT Bearer flow via an External Client App with Digital
Signatures. The username-password OAuth flow is blocked by default on
Agentforce / Summer '23+ orgs, so we sign a JWT assertion with our
private key and exchange it for an access token.

Status-field name handling: the rule's parameter_mapping uses "new_status"
to provide the target value. The SF field name itself (`Status__c` custom
field vs the built-in Status) is probed at first call and cached for the
session.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from functools import lru_cache
from pathlib import Path

import jwt
import requests
from simple_salesforce import Salesforce

from truthkeeper.actions.result import ExecutionResult

logger = logging.getLogger(__name__)

_STATUS_FIELD_CANDIDATES = ("Status__c", "Status", "Account_Status__c")


def _load_private_key() -> str:
    """Resolve the JWT private key from one of three env-var forms."""
    if pem := os.environ.get("SF_JWT_PRIVATE_KEY"):
        return pem
    if b64 := os.environ.get("SF_JWT_PRIVATE_KEY_B64"):
        return base64.b64decode(b64).decode("utf-8")
    if path := os.environ.get("SF_JWT_PRIVATE_KEY_PATH"):
        return Path(path).read_text()
    raise RuntimeError(
        "JWT auth selected but no private key found. Set one of: "
        "SF_JWT_PRIVATE_KEY, SF_JWT_PRIVATE_KEY_B64, SF_JWT_PRIVATE_KEY_PATH."
    )


def _required_jwt_env() -> dict[str, str]:
    keys = ("SF_USERNAME", "SF_JWT_CONSUMER_KEY", "SF_LOGIN_HOST")
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Salesforce JWT credentials missing: {', '.join(missing)}. "
            "Add to validation/.env (local) or Cloud Run env (prod)."
        )
    return {k: os.environ[k] for k in keys}


@lru_cache(maxsize=1)
def _client() -> Salesforce:
    env = _required_jwt_env()
    audience = f"https://{env['SF_LOGIN_HOST']}"
    token_url = f"{audience}/services/oauth2/token"

    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": env["SF_JWT_CONSUMER_KEY"],
            "sub": env["SF_USERNAME"],
            "aud": audience,
            "exp": now + 180,
        },
        _load_private_key(),
        algorithm="RS256",
    )

    response = requests.post(
        token_url,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"JWT auth failed: {response.status_code} {response.text[:500]}"
        )
    payload = response.json()
    return Salesforce(
        instance_url=payload["instance_url"],
        session_id=payload["access_token"],
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

"""Salesforce Developer Edition seeder.

Auth: OAuth 2.0 JWT Bearer flow via an External Client App with Digital
Signatures. The username-password OAuth flow is blocked by default in
Agentforce / Summer '23+ DE orgs, so we sign a JWT assertion with our
private key and exchange it for an access token.

Falls back to OAuth username-password flow if SF_JWT_CONSUMER_KEY is not
configured (kept for backwards compatibility with older org setups).

Idempotency: query by Account.Name; if exists, update fields; otherwise
create. Contacts are upserted by Email. teardown.py handles deletes.
"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

import jwt
import requests
from simple_salesforce import Salesforce  # type: ignore[import-untyped]

from seed.config import get_settings
from seed.models import SeedCatalog, SeedCustomer

log = logging.getLogger(__name__)


def _load_private_key() -> str:
    """Resolve the JWT private key from one of three env-var forms."""
    s = get_settings()
    if s.sf_jwt_private_key:
        return s.sf_jwt_private_key
    if s.sf_jwt_private_key_b64:
        return base64.b64decode(s.sf_jwt_private_key_b64).decode("utf-8")
    if s.sf_jwt_private_key_path:
        return Path(s.sf_jwt_private_key_path).read_text()
    raise RuntimeError(
        "JWT auth selected but no private key found. Set one of: "
        "SF_JWT_PRIVATE_KEY, SF_JWT_PRIVATE_KEY_B64, SF_JWT_PRIVATE_KEY_PATH."
    )


def _jwt_client() -> Salesforce:
    """Authenticate via OAuth 2.0 JWT Bearer flow."""
    s = get_settings()
    host = s.sf_login_host or "login.salesforce.com"
    audience = f"https://{host}"
    token_url = f"{audience}/services/oauth2/token"

    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": s.sf_jwt_consumer_key,
            "sub": s.sf_username,
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
        # SF returns useful error JSON on 4xx — surface it for debugging.
        raise RuntimeError(
            f"JWT auth failed: {response.status_code} {response.text[:500]}"
        )
    payload = response.json()
    return Salesforce(
        instance_url=payload["instance_url"],
        session_id=payload["access_token"],
    )


def _password_grant_client() -> Salesforce:
    """Legacy OAuth username-password flow (kept for old org setups)."""
    s = get_settings()
    if not (s.sf_consumer_key and s.sf_consumer_secret):
        # Older SOAP fallback if nothing OAuth is configured at all.
        return Salesforce(
            username=s.sf_username,
            password=s.sf_password,
            security_token=s.sf_security_token,
            domain=s.sf_domain,
        )

    host = s.sf_login_host or f"{s.sf_domain}.salesforce.com"
    token_url = f"https://{host}/services/oauth2/token"
    response = requests.post(
        token_url,
        data={
            "grant_type": "password",
            "client_id": s.sf_consumer_key,
            "client_secret": s.sf_consumer_secret,
            "username": s.sf_username,
            "password": f"{s.sf_password}{s.sf_security_token}",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return Salesforce(
        instance_url=payload["instance_url"],
        session_id=payload["access_token"],
    )


def _client() -> Salesforce:
    """Authenticate, preferring JWT Bearer if configured."""
    s = get_settings()
    if s.sf_jwt_consumer_key:
        return _jwt_client()
    return _password_grant_client()


def _upsert_account(sf: Salesforce, c: SeedCustomer) -> str:
    """Upsert an Account by Name; return its Id."""
    assert c.salesforce is not None
    p = c.salesforce
    existing = sf.query(
        f"SELECT Id FROM Account WHERE Name = '{p.account_name}' LIMIT 1"
    )
    payload = {
        "Name": p.account_name,
        "Type": "Customer",
        "Description": f"[seed:{c.seed_id}] {c.notes}",
    }
    if existing["totalSize"] > 0:
        account_id = existing["records"][0]["Id"]
        sf.Account.update(account_id, payload)
        return account_id
    return sf.Account.create(payload)["id"]


def _upsert_contact(sf: Salesforce, c: SeedCustomer, account_id: str) -> None:
    assert c.salesforce is not None
    p = c.salesforce
    existing = sf.query(
        f"SELECT Id FROM Contact WHERE Email = '{p.contact_email}' LIMIT 1"
    )
    payload = {
        "FirstName": c.first_name,
        "LastName": c.last_name,
        "Email": p.contact_email,
        "AccountId": account_id,
        "Description": f"[seed:{c.seed_id}] status={p.status}",
    }
    if existing["totalSize"] > 0:
        sf.Contact.update(existing["records"][0]["Id"], payload)
    else:
        sf.Contact.create(payload)


def upsert(catalog: SeedCatalog) -> None:
    sf = _client()
    for c in catalog.customers:
        if c.salesforce is None:
            log.info("Skipping %s in Salesforce (intentionally absent)", c.seed_id)
            continue
        account_id = _upsert_account(sf, c)
        _upsert_contact(sf, c, account_id)
        log.info("Upserted %s in Salesforce", c.seed_id)

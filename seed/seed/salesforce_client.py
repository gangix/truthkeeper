"""Salesforce Developer Edition seeder.

Auth: OAuth Username-Password flow via an External Client App.
Newer Agentforce orgs disable SOAP API login by default, so we authenticate
through the OAuth /services/oauth2/token endpoint using a Connected App's
consumer key + secret plus the user's username/password+security_token.

Idempotency: query by Account.Name; if exists, update fields; otherwise
create. Contacts are upserted by Email. teardown.py handles deletes.
"""

from __future__ import annotations

import logging

import requests
from simple_salesforce import Salesforce  # type: ignore[import-untyped]

from seed.config import get_settings
from seed.models import SeedCatalog, SeedCustomer

log = logging.getLogger(__name__)


def _client() -> Salesforce:
    """Authenticate via OAuth Username-Password flow.

    Newer Agentforce orgs require an External Client App's consumer key +
    secret + the user's username/password+security_token, called against the
    org's My Domain. Falls back to legacy SOAP login if consumer credentials
    aren't configured (works on older Developer Edition orgs).
    """
    s = get_settings()

    if s.sf_consumer_key and s.sf_consumer_secret:
        # OAuth Username-Password flow (required for orgs with SOAP disabled).
        # Newer Agentforce orgs require the org's My Domain URL — fall back to
        # login.salesforce.com only when SF_LOGIN_HOST is not provided.
        host = s.sf_login_host or f"{s.sf_domain}.salesforce.com"
        token_url = f"https://{host}/services/oauth2/token"
        response = requests.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": s.sf_consumer_key,
                "client_secret": s.sf_consumer_secret,
                "username": s.sf_username,
                # Password and security token are concatenated for this flow.
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

    # Legacy SOAP path — works on older orgs where SOAP API login is enabled.
    return Salesforce(
        username=s.sf_username,
        password=s.sf_password,
        security_token=s.sf_security_token,
        domain=s.sf_domain,
    )


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
    # SF custom-field convention varies — for the demo we keep status in Description.
    # If you've created a custom field __c, switch this to use it.
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

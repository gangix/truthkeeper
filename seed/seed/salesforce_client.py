"""Salesforce Developer Edition seeder.

Idempotency strategy: query by Account.Name; if exists, update fields;
otherwise create. Contacts are upserted by Email. We do NOT delete records
this seeder doesn't recognize — teardown is in teardown.py.
"""

from __future__ import annotations

import logging

from simple_salesforce import Salesforce  # type: ignore[import-untyped]

from seed.config import get_settings
from seed.models import SeedCatalog, SeedCustomer

log = logging.getLogger(__name__)


def _client() -> Salesforce:
    s = get_settings()
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

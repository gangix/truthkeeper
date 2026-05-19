"""Reset all three SaaS sandboxes to a clean state (delete only seed records).

Recognizes seeded records via:
- Salesforce:    Description prefix '[seed:'
- Stripe:        metadata.seed == 'truthkeeper'
- HubSpot:       tk_seed_id property is non-empty

USE WITH CARE. This deletes data, but only in our sandboxes — guard against
running against a production Stripe key (we check sk_test_ prefix).
"""

from __future__ import annotations

import logging

import stripe
from hubspot import HubSpot
from hubspot.crm.contacts.exceptions import ApiException as HSException
from simple_salesforce import Salesforce  # type: ignore[import-untyped]

from seed.config import get_settings
from seed.salesforce_client import _client as _sf_client  # reuses the same auth path


def teardown_salesforce(log: logging.Logger) -> None:
    sf = _sf_client()
    # SOQL can't filter on Description (long text field), so we match on email
    # pattern. All seeded contact emails end in .example or .example.com.
    contacts = sf.query(
        "SELECT Id, AccountId FROM Contact "
        "WHERE Email LIKE '%.example' OR Email LIKE '%.example.com'"
    )
    account_ids = {r["AccountId"] for r in contacts["records"] if r["AccountId"]}
    for r in contacts["records"]:
        sf.Contact.delete(r["Id"])
    for aid in account_ids:
        sf.Account.delete(aid)
    log.info("Salesforce: deleted %d contacts and %d accounts",
             contacts["totalSize"], len(account_ids))


def teardown_stripe(log: logging.Logger) -> None:
    s = get_settings()
    if not s.stripe_secret_key.startswith("sk_test_"):
        raise RuntimeError("Refusing to teardown against non-test Stripe key")
    stripe.api_key = s.stripe_secret_key
    deleted = 0
    customers = stripe.Customer.search(query='metadata["seed"]:"truthkeeper"', limit=100)
    for c in customers.data:
        stripe.Customer.delete(c.id)
        deleted += 1
    log.info("Stripe: deleted %d customers", deleted)


def teardown_hubspot(log: logging.Logger) -> None:
    s = get_settings()
    client = HubSpot(access_token=s.hubspot_access_token)
    deleted = 0
    # Pull all contacts, filter by our seed tag
    after: str | None = None
    while True:
        page = client.crm.contacts.basic_api.get_page(
            limit=100, after=after, properties=["tk_seed_id"]
        )
        for contact in page.results:
            if (contact.properties or {}).get("tk_seed_id"):
                try:
                    client.crm.contacts.basic_api.archive(contact_id=contact.id)
                    deleted += 1
                except HSException as e:
                    log.warning("Failed to archive contact %s: %s", contact.id, e)
        if not page.paging or not page.paging.next:
            break
        after = page.paging.next.after
    log.info("HubSpot: archived %d contacts", deleted)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    log = logging.getLogger("seed.teardown")
    log.info("=== Tearing down Salesforce ===")
    teardown_salesforce(log)
    log.info("=== Tearing down Stripe ===")
    teardown_stripe(log)
    log.info("=== Tearing down HubSpot ===")
    teardown_hubspot(log)
    log.info("Teardown complete.")


if __name__ == "__main__":
    main()

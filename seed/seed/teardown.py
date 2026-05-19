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


def _sf_client() -> Salesforce:
    s = get_settings()
    return Salesforce(
        username=s.sf_username,
        password=s.sf_password,
        security_token=s.sf_security_token,
        domain=s.sf_domain,
    )


def teardown_salesforce(log: logging.Logger) -> None:
    sf = _sf_client()
    contacts = sf.query("SELECT Id FROM Contact WHERE Description LIKE '[seed:%'")
    for r in contacts["records"]:
        sf.Contact.delete(r["Id"])
    accounts = sf.query("SELECT Id FROM Account WHERE Description LIKE '[seed:%'")
    for r in accounts["records"]:
        sf.Account.delete(r["Id"])
    log.info("Salesforce: deleted %d contacts and %d accounts",
             contacts["totalSize"], accounts["totalSize"])


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

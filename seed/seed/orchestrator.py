"""Run all three seeders in order against a SeedCatalog.

Salesforce first (slowest, OAuth-y), then Stripe (test mode is fast),
then HubSpot. Aborts on first failure (Plan 3+ work doesn't need
partial state).
"""

from __future__ import annotations

import logging

from seed.data import build_catalog
from seed.hubspot_client import upsert as upsert_hubspot
from seed.salesforce_client import upsert as upsert_salesforce
from seed.stripe_client import upsert as upsert_stripe


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    log = logging.getLogger("seed.orchestrator")

    catalog = build_catalog()
    log.info("Catalog built: %d customers, %d discrepancies",
             catalog.count(), len(catalog.discrepancies()))

    log.info("=== Seeding Salesforce ===")
    upsert_salesforce(catalog)
    log.info("=== Seeding Stripe ===")
    upsert_stripe(catalog)
    log.info("=== Seeding HubSpot ===")
    upsert_hubspot(catalog)

    log.info("All systems seeded successfully.")


if __name__ == "__main__":
    main()

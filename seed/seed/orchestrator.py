"""Run seeders against a SeedCatalog.

Set SEED_SKIP=salesforce,stripe,hubspot (any subset, comma-separated) to
skip systems whose auth isn't ready. Useful while one provider's setup
is still being worked through.
"""

from __future__ import annotations

import logging
import os

from seed.data import build_catalog
from seed.hubspot_client import upsert as upsert_hubspot
from seed.salesforce_client import upsert as upsert_salesforce
from seed.stripe_client import upsert as upsert_stripe


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    log = logging.getLogger("seed.orchestrator")

    skip = {s.strip().lower() for s in os.environ.get("SEED_SKIP", "").split(",") if s.strip()}
    catalog = build_catalog()
    log.info("Catalog built: %d customers, %d discrepancies",
             catalog.count(), len(catalog.discrepancies()))
    if skip:
        log.info("Skipping systems (per SEED_SKIP): %s", ", ".join(sorted(skip)))

    for name, fn in [
        ("salesforce", upsert_salesforce),
        ("stripe", upsert_stripe),
        ("hubspot", upsert_hubspot),
    ]:
        if name in skip:
            log.info("=== Skipping %s ===", name.capitalize())
            continue
        log.info("=== Seeding %s ===", name.capitalize())
        fn(catalog)

    log.info("Seed run complete.")


if __name__ == "__main__":
    main()

"""HubSpot Developer-account seeder.

Idempotency strategy: use the email-based search API to find contacts;
create or update properties. Sequences are NOT enrolled here — for the
demo we encode the "intended sequence" in a custom contact property
`current_sequence` (string) that we set during seeding. The BigQuery sync
exposes this property and Plan 3's rules read it as a stand-in for true
sequence membership. (HubSpot's sequence-enrollment API requires Sales Hub
Pro, which dev accounts don't include.)
"""

from __future__ import annotations

import logging

from hubspot import HubSpot
from hubspot.crm.contacts import (
    SimplePublicObjectInputForCreate,
)
from hubspot.crm.contacts.exceptions import ApiException

from seed.config import get_settings
from seed.models import SeedCatalog, SeedCustomer

log = logging.getLogger(__name__)


def _client() -> HubSpot:
    s = get_settings()
    return HubSpot(access_token=s.hubspot_access_token)


def _seed_one(client: HubSpot, c: SeedCustomer) -> None:
    assert c.hubspot is not None
    p = c.hubspot

    properties = {
        "email": p.contact_email,
        "firstname": c.first_name,
        "lastname": c.last_name,
        "company": c.company_name,
        # We tag every seeded contact so teardown can find them.
        "tk_seed_id": c.seed_id,
        "tk_current_sequence": p.in_sequence,
    }
    try:
        existing = client.crm.contacts.basic_api.get_by_id(
            contact_id=p.contact_email, id_property="email"
        )
        client.crm.contacts.basic_api.update(
            contact_id=existing.id,
            simple_public_object_input={"properties": properties},
        )
    except ApiException as e:
        if e.status == 404:
            client.crm.contacts.basic_api.create(
                simple_public_object_input_for_create=SimplePublicObjectInputForCreate(
                    properties=properties,
                ),
            )
        else:
            raise
    log.info("Seeded %s in HubSpot", c.seed_id)


def upsert(catalog: SeedCatalog) -> None:
    client = _client()
    for c in catalog.customers:
        if c.hubspot is None:
            log.info("Skipping %s in HubSpot (intentionally absent)", c.seed_id)
            continue
        _seed_one(client, c)

"""Sanity tests on the seed catalog shape (data added in next task)."""

from __future__ import annotations

import pytest

from seed.models import (
    HubSpotPresence,
    SalesforcePresence,
    SeedCatalog,
    SeedCustomer,
    StripePresence,
)


def make_minimal_customer() -> SeedCustomer:
    return SeedCustomer(
        seed_id="C001",
        first_name="Test",
        last_name="User",
        company_name="Test Co",
        salesforce=SalesforcePresence(
            account_name="Test Co",
            contact_email="test@example.com",
        ),
        stripe=StripePresence(customer_email="test@example.com"),
        hubspot=HubSpotPresence(contact_email="test@example.com"),
    )


def test_minimal_customer_validates() -> None:
    c = make_minimal_customer()
    assert c.discrepancy == "NONE"


def test_invalid_discrepancy_id_rejected() -> None:
    with pytest.raises(ValueError):
        SeedCustomer(
            seed_id="C002",
            first_name="X",
            last_name="Y",
            company_name="Z",
            salesforce=None,
            stripe=None,
            hubspot=None,
            discrepancy="NOT_A_REAL_ID",  # type: ignore[arg-type]
        )


def test_catalog_can_count_and_filter() -> None:
    cat = SeedCatalog(customers=[make_minimal_customer()])
    assert cat.count() == 1
    assert cat.discrepancies() == []

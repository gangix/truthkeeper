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


def test_catalog_has_50_customers_and_5_discrepancies(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub the env so config.get_settings() works in tests without a .env
    monkeypatch.setenv("SF_USERNAME", "test")
    monkeypatch.setenv("SF_PASSWORD", "test")
    monkeypatch.setenv("SF_SECURITY_TOKEN", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "pat-x")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "1")
    monkeypatch.setenv("SEED_BASE_DATE", "2026-05-19")
    # Bust the lru_cache so the new env takes effect
    from seed import config
    config.get_settings.cache_clear()

    from seed.data import build_catalog

    cat = build_catalog()
    assert cat.count() == 50
    assert len(cat.discrepancies()) == 5
    disc_ids = sorted(c.discrepancy for c in cat.discrepancies())
    assert disc_ids == [
        "D1_revenue_leak_missed_churn",
        "D2_trial_paid_but_sf_missed",
        "D3_identity_fracture",
        "D4_refunded_but_marketed",
        "D5_orphaned_stripe_customer",
    ]

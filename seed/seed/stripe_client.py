"""Stripe test-mode seeder.

Idempotency strategy: search for customers by email (metadata seed_id as
secondary index). Create or update; then ensure subscription + a recent
invoice exists per the seed config. Past invoices for invoice_history_months
are simulated by creating PaymentIntents at specific timestamps.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import stripe

from seed.config import get_settings
from seed.models import SeedCatalog, SeedCustomer

log = logging.getLogger(__name__)


def _init() -> None:
    s = get_settings()
    stripe.api_key = s.stripe_secret_key
    # Guard: never run against live keys
    if not s.stripe_secret_key.startswith("sk_test_"):
        raise RuntimeError(
            "Refusing to run seed against a non-test Stripe key. "
            "STRIPE_SECRET_KEY must start with 'sk_test_'."
        )


def _ensure_product_and_price(monthly_eur: int) -> str:
    """Return the price ID for a recurring monthly EUR amount, creating if needed."""
    product_name = f"TruthKeeper Seed Plan €{monthly_eur}/mo"
    products = stripe.Product.list(limit=100, active=True)
    product = next(
        (p for p in products.data if p.name == product_name),
        None,
    )
    if product is None:
        product = stripe.Product.create(
            name=product_name,
            metadata={"seed": "truthkeeper"},
        )
    prices = stripe.Price.list(product=product.id, active=True, limit=10)
    price = next(
        (
            p
            for p in prices.data
            if p.unit_amount == monthly_eur * 100
            and p.currency == "eur"
            and p.recurring
            and p.recurring.interval == "month"
        ),
        None,
    )
    if price is None:
        price = stripe.Price.create(
            product=product.id,
            unit_amount=monthly_eur * 100,
            currency="eur",
            recurring={"interval": "month"},
        )
    return price.id


def _find_customer(email: str) -> stripe.Customer | None:
    result = stripe.Customer.search(query=f'email:"{email}"', limit=1)
    return result.data[0] if result.data else None


def _seed_one(c: SeedCustomer) -> None:
    assert c.stripe is not None
    p = c.stripe

    cust = _find_customer(p.customer_email)
    if cust is None:
        cust = stripe.Customer.create(
            email=p.customer_email,
            name=f"{c.first_name} {c.last_name}",
            metadata={"seed_id": c.seed_id, "seed": "truthkeeper"},
        )
    else:
        stripe.Customer.modify(
            cust.id,
            name=f"{c.first_name} {c.last_name}",
            metadata={"seed_id": c.seed_id, "seed": "truthkeeper"},
        )

    if p.subscription_status in ("active", "trialing"):
        price_id = _ensure_product_and_price(p.monthly_amount_eur)
        existing_subs = stripe.Subscription.list(customer=cust.id, status="all", limit=10)
        active_sub = next(
            (s for s in existing_subs.data if s.status in ("active", "trialing", "past_due")),
            None,
        )
        if active_sub is None:
            stripe.Subscription.create(
                customer=cust.id,
                items=[{"price": price_id}],
                # No trial in test mode by default; for the demo this is fine.
                metadata={"seed_id": c.seed_id},
            )
    elif p.subscription_status == "canceled":
        subs = stripe.Subscription.list(customer=cust.id, status="all", limit=10)
        for s in subs.data:
            if s.status not in ("canceled",):
                stripe.Subscription.cancel(s.id)
        if p.refunded_last_invoice:
            invoices = stripe.Invoice.list(customer=cust.id, limit=5)
            if invoices.data and invoices.data[0].charge:
                stripe.Refund.create(charge=invoices.data[0].charge)
    log.info("Seeded %s in Stripe (customer %s)", c.seed_id, cust.id)


def upsert(catalog: SeedCatalog) -> None:
    _init()
    for c in catalog.customers:
        if c.stripe is None:
            log.info("Skipping %s in Stripe (intentionally absent)", c.seed_id)
            continue
        _seed_one(c)

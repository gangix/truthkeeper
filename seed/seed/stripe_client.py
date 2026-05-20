"""Stripe test-mode seeder.

Idempotency strategy: search for customers by email (metadata seed_id as
secondary index). Create or update; then ensure subscription + a recent
invoice exists per the seed config.

Three paid-invoice modes:

  * Default (paid_invoice_count == 0 and refunded_last_invoice == False):
    create the subscription with collection_method=send_invoice. Invoices
    remain in `open` status — fine for rules that only inspect subscription
    status.

  * paid_invoice_count > 0: after creating the subscription, mark its
    open invoices as paid via Invoice.pay(paid_out_of_band=True). If more
    paid invoices are needed than exist, backfill them with standalone
    InvoiceItem + Invoice + finalize + pay sequences (one per past month).
    Used by D2 (paid annual invoice signals upsell) and D5 (multi-month
    payment history signals long tenure).

  * refunded_last_invoice == True: the D4 path — needs a real Stripe
    charge to refund. Cancels any send-invoice subscriptions, attaches a
    test card, creates a new charge_automatically subscription, lets the
    auto-charge land, cancels it, then refunds the charge.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import stripe

from seed.config import get_settings
from seed.models import SeedCatalog, SeedCustomer

log = logging.getLogger(__name__)


def _init() -> None:
    s = get_settings()
    stripe.api_key = s.stripe_secret_key
    if not s.stripe_secret_key.startswith("sk_test_"):
        raise RuntimeError(
            "Refusing to run seed against a non-test Stripe key. "
            "STRIPE_SECRET_KEY must start with 'sk_test_'."
        )


def _ensure_product_and_price(monthly_eur: int) -> str:
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


def _ensure_default_payment_method(customer_id: str) -> str:
    """Attach a test card and mark it default. Returns the PaymentMethod id."""
    existing = stripe.PaymentMethod.list(customer=customer_id, type="card", limit=1)
    if existing.data:
        pm_id = existing.data[0].id
    else:
        # pm_card_visa is a Stripe-provided shared test PaymentMethod;
        # attaching it to a customer creates a customer-scoped copy.
        pm = stripe.PaymentMethod.attach("pm_card_visa", customer=customer_id)
        pm_id = pm.id
    stripe.Customer.modify(
        customer_id,
        invoice_settings={"default_payment_method": pm_id},
    )
    return pm_id


def _pay_open_invoices(customer_id: str, target_count: int) -> int:
    """Mark up to target_count open invoices as paid (out-of-band).

    Returns the number actually paid in this run.
    """
    paid_now = 0
    invoices = stripe.Invoice.list(customer=customer_id, status="open", limit=50)
    for inv in invoices.data:
        if paid_now >= target_count:
            break
        try:
            stripe.Invoice.pay(inv.id, paid_out_of_band=True)
            paid_now += 1
            log.info("  paid invoice %s out-of-band for %s", inv.id, customer_id)
        except stripe.error.InvalidRequestError as exc:
            log.warning("  could not pay invoice %s: %s", inv.id, exc)
    return paid_now


def _backfill_paid_invoices(
    customer_id: str,
    needed: int,
    monthly_eur: int,
    months_back_start: int,
) -> int:
    """Create `needed` standalone past-dated paid invoices for the customer.

    Each invoice is a single InvoiceItem with the monthly amount, finalized
    and paid out-of-band. Backdating is via `metadata.synthetic_date` because
    Stripe's `created` is server-controlled — the agent's reasoning still has
    the synthetic date if it wants timeline narration.
    """
    created = 0
    for i in range(needed):
        offset_months = months_back_start + i
        synthetic_date = (
            datetime.now(timezone.utc) - timedelta(days=30 * offset_months)
        ).date().isoformat()
        try:
            # Create the invoice first, then link the InvoiceItem to it
            # explicitly via `invoice=`. The pending-items auto-pull behavior
            # is unreliable and produced total=0 invoices in earlier runs.
            inv = stripe.Invoice.create(
                customer=customer_id,
                collection_method="send_invoice",
                days_until_due=30,
                metadata={
                    "seed": "truthkeeper",
                    "synthetic_date": synthetic_date,
                },
            )
            stripe.InvoiceItem.create(
                customer=customer_id,
                invoice=inv.id,
                amount=monthly_eur * 100,
                currency="eur",
                description=f"TruthKeeper seed: backdated €{monthly_eur} for {synthetic_date}",
                metadata={
                    "seed": "truthkeeper",
                    "synthetic_date": synthetic_date,
                },
            )
            inv = stripe.Invoice.finalize_invoice(inv.id)
            stripe.Invoice.pay(inv.id, paid_out_of_band=True)
            created += 1
            log.info(
                "  backfilled paid invoice %s (%s, %d cents) for %s",
                inv.id,
                synthetic_date,
                inv.total,
                customer_id,
            )
        except stripe.error.StripeError as exc:
            log.warning("  could not backfill invoice for %s: %s", customer_id, exc)
            break
    return created


def _count_paid_invoices(customer_id: str) -> int:
    paid = stripe.Invoice.list(customer=customer_id, status="paid", limit=100)
    return len(paid.data)


def _handle_refunded_path(c: SeedCustomer, customer_id: str) -> None:
    """D4 — refund the most recent unrefunded charge for this customer.

    Idempotency:
      * If any charge is already refunded → done.
      * Else if any successful unrefunded charge exists → refund the latest.
      * Else (no charges at all) → set up a payment method, create a
        charge_automatically subscription so a real charge lands, cancel
        the subscription, then refund the resulting charge.

    The invoice.charge / invoice.payment_intent fields are inconsistently
    populated in newer Stripe API versions, so refund targeting goes
    customer → Charge list → refund(charge_id) instead of via the invoice.
    """
    existing_charges = stripe.Charge.list(customer=customer_id, limit=20)
    if any(ch.refunded for ch in existing_charges.data):
        log.info("D004 already has a refunded charge; skipping")
        return

    unrefunded = [
        ch
        for ch in existing_charges.data
        if not ch.refunded and ch.status == "succeeded"
    ]
    if unrefunded:
        # Cancel any non-canceled subs first so the demo state is "canceled +
        # refunded" rather than "active subscription with refunded charge".
        existing_subs = stripe.Subscription.list(customer=customer_id, status="all", limit=10)
        for s in existing_subs.data:
            if s.status != "canceled":
                stripe.Subscription.cancel(s.id)
        # Charge.list returns most-recent first.
        ch = unrefunded[0]
        refund = stripe.Refund.create(charge=ch.id)
        log.info(
            "D004 refund %s created against existing charge %s (customer %s)",
            refund.id,
            ch.id,
            customer_id,
        )
        return

    # No charges at all — set up the auto-charge path from scratch.
    existing_subs = stripe.Subscription.list(customer=customer_id, status="all", limit=10)
    for s in existing_subs.data:
        if s.status != "canceled":
            stripe.Subscription.cancel(s.id)

    pm_id = _ensure_default_payment_method(customer_id)
    price_id = _ensure_product_and_price(c.stripe.monthly_amount_eur)

    sub = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        collection_method="charge_automatically",
        default_payment_method=pm_id,
        metadata={"seed_id": c.seed_id, "purpose": "d004_refund_flow"},
    )

    # Wait for the auto-charge by re-listing charges.
    sub_charges = stripe.Charge.list(customer=customer_id, limit=20)
    new_charges = [
        ch for ch in sub_charges.data if ch.status == "succeeded" and not ch.refunded
    ]
    if not new_charges:
        log.warning(
            "D004 subscription %s did not produce a chargeable result for %s",
            sub.id,
            customer_id,
        )
        return

    stripe.Subscription.cancel(sub.id)
    refund = stripe.Refund.create(charge=new_charges[0].id)
    log.info(
        "D004 refund %s created against new charge %s (customer %s)",
        refund.id,
        new_charges[0].id,
        customer_id,
    )


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

    if p.refunded_last_invoice:
        _handle_refunded_path(c, cust.id)
        log.info("Seeded %s in Stripe (customer %s, refunded path)", c.seed_id, cust.id)
        return

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
                collection_method="send_invoice",
                days_until_due=30,
                metadata={"seed_id": c.seed_id},
            )

        if p.paid_invoice_count > 0:
            already_paid = _count_paid_invoices(cust.id)
            still_needed = max(0, p.paid_invoice_count - already_paid)
            if still_needed > 0:
                paid_from_open = _pay_open_invoices(cust.id, still_needed)
                still_needed -= paid_from_open
                if still_needed > 0:
                    _backfill_paid_invoices(
                        customer_id=cust.id,
                        needed=still_needed,
                        monthly_eur=p.monthly_amount_eur,
                        months_back_start=1,
                    )

    elif p.subscription_status == "canceled":
        subs = stripe.Subscription.list(customer=cust.id, status="all", limit=10)
        for s in subs.data:
            if s.status != "canceled":
                stripe.Subscription.cancel(s.id)

    log.info("Seeded %s in Stripe (customer %s)", c.seed_id, cust.id)


def upsert(catalog: SeedCatalog) -> None:
    _init()
    for c in catalog.customers:
        if c.stripe is None:
            log.info("Skipping %s in Stripe (intentionally absent)", c.seed_id)
            continue
        _seed_one(c)

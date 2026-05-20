"""The deterministic seed catalog: 50 customers, 5 deliberate discrepancies.

Maps to brief §6. Each discrepancy is a single SeedCustomer whose three
per-system presences are intentionally inconsistent. The other 45 are
"normal" customers consistent across all systems, providing realistic
background noise for the reconciliation rules to ignore.
"""

from __future__ import annotations

from datetime import date, timedelta

from seed.config import get_settings
from seed.models import (
    HubSpotPresence,
    SalesforcePresence,
    SeedCatalog,
    SeedCustomer,
    StripePresence,
)


# ── The 5 deliberate discrepancies ─────────────────────────────────────────

def _build_discrepancies(base: date) -> list[SeedCustomer]:
    return [
        # D1: Acme churned 23 days ago in product, Stripe still billing
        SeedCustomer(
            seed_id="D001",
            first_name="Anna",
            last_name="Chen",
            company_name="Acme Corp",
            salesforce=SalesforcePresence(
                account_name="Acme Corp",
                contact_email="anna.chen@acme.example.com",
                status="Churned",
                churn_date=base - timedelta(days=23),
            ),
            stripe=StripePresence(
                customer_email="anna.chen@acme.example.com",
                subscription_status="active",
                monthly_amount_eur=89,
                last_invoice_date=base - timedelta(days=10),
                invoice_history_months=3,  # 2 months billed AFTER churn
            ),
            hubspot=HubSpotPresence(
                contact_email="anna.chen@acme.example.com",
                in_sequence="Engaged Trial",  # also wrong — should be removed
            ),
            discrepancy="D1_revenue_leak_missed_churn",
            notes="Webhook product→Stripe failed 23d ago. €207 leaked, growing €89/mo.",
        ),
        # D2: Beta paid annual in Stripe, Salesforce still Trial
        SeedCustomer(
            seed_id="D002",
            first_name="Ben",
            last_name="Park",
            company_name="Beta Industries",
            salesforce=SalesforcePresence(
                account_name="Beta Industries",
                contact_email="ben.park@beta.example.com",
                status="Trial",  # WRONG — should be Paid Annual
            ),
            stripe=StripePresence(
                customer_email="ben.park@beta.example.com",
                subscription_status="active",
                monthly_amount_eur=400,  # 4800/12
                last_invoice_date=_last_friday(base),
                invoice_history_months=1,
                paid_invoice_count=1,  # the paid annual invoice — D2's whole point
            ),
            hubspot=HubSpotPresence(
                contact_email="ben.park@beta.example.com",
                in_sequence="Engaged Trial",
            ),
            discrepancy="D2_trial_paid_but_sf_missed",
            notes="€4,800 annual invoice paid in Stripe last Friday; SF Account.Status still Trial. Sales rep doesn't know to assign CSM.",
        ),
        # D3: Identity fracture — same human, two emails across systems
        SeedCustomer(
            seed_id="D003",
            first_name="John",
            last_name="Smith",
            company_name="Gamma LLC",
            salesforce=SalesforcePresence(
                account_name="Gamma LLC",
                contact_email="j.smith@gamma.example.com",  # short alias
                status="Paid Annual",
            ),
            stripe=StripePresence(
                customer_email="john.smith@gamma.example.com",  # canonical
                subscription_status="active",
                monthly_amount_eur=149,
                last_invoice_date=base - timedelta(days=5),
                invoice_history_months=4,
            ),
            hubspot=HubSpotPresence(
                contact_email="john.smith@gamma.example.com",  # canonical
                in_sequence="Paying Customer Onboarding",
            ),
            discrepancy="D3_identity_fracture",
            notes="Same person; SF has j.smith@, HubSpot has john.smith@. Broken attribution / two records on the same human.",
        ),
        # D4: Refunded in Stripe last week, HubSpot still in active onboarding sequence
        SeedCustomer(
            seed_id="D004",
            first_name="Diana",
            last_name="Vega",
            company_name="Delta Co",
            salesforce=SalesforcePresence(
                account_name="Delta Co",
                contact_email="diana.vega@delta.example.com",
                status="Churned",
            ),
            stripe=StripePresence(
                customer_email="diana.vega@delta.example.com",
                subscription_status="canceled",
                monthly_amount_eur=89,
                last_invoice_date=base - timedelta(days=7),
                refunded_last_invoice=True,
                invoice_history_months=2,
            ),
            hubspot=HubSpotPresence(
                contact_email="diana.vega@delta.example.com",
                in_sequence="Paying Customer Onboarding",  # WRONG — should be Win Back
            ),
            discrepancy="D4_refunded_but_marketed",
            notes="Full refund last week; HubSpot still emailing onboarding tips. Customer experience risk.",
        ),
        # D5: Orphaned Stripe customer — exists in Stripe, never made it to SF
        SeedCustomer(
            seed_id="D005",
            first_name="Eric",
            last_name="Olsen",
            company_name="Epsilon Holdings",
            salesforce=None,  # NEVER created in Salesforce — that's the bug
            stripe=StripePresence(
                customer_email="eric.olsen@epsilon.example.com",
                subscription_status="active",
                monthly_amount_eur=199,
                last_invoice_date=base - timedelta(days=3),
                invoice_history_months=6,
                paid_invoice_count=6,  # 6 months of payments — D5's revenue-attribution evidence
            ),
            hubspot=HubSpotPresence(
                contact_email="eric.olsen@epsilon.example.com",
                in_sequence="Paying Customer Onboarding",
            ),
            discrepancy="D5_orphaned_stripe_customer",
            notes="6 months of Stripe payments; SF Account never created (webhook failure). Sales has zero record.",
        ),
    ]


# ── 45 "normal" customers (background) ─────────────────────────────────────

_NORMAL_FIRST = [
    "Alex", "Sam", "Riley", "Jordan", "Casey", "Morgan", "Jamie", "Quinn",
    "Drew", "Skylar", "Reese", "Charlie", "Logan", "Avery", "Cameron",
    "Devon", "Emerson", "Finley", "Gray", "Harper", "Ira", "Jules",
    "Kai", "Lane", "Maya", "Nico", "Owen", "Paige", "Remy", "Sage",
    "Tatum", "Uma", "Vesper", "Wren", "Xen", "Yara", "Zion", "Indigo",
    "Justice", "Kendall", "Lennon", "Marlowe", "Noor", "Ocean", "Phoenix",
]


def _build_normals(base: date) -> list[SeedCustomer]:
    out: list[SeedCustomer] = []
    for i, first in enumerate(_NORMAL_FIRST):
        company = f"{first} Industries"
        email = f"{first.lower()}@{company.lower().replace(' ', '')}.example.com"
        status = "Paid Annual" if i % 2 == 0 else "Trial"
        sub_status = "active" if i % 2 == 0 else "trialing"
        sequence = "Paying Customer Onboarding" if i % 2 == 0 else "Engaged Trial"
        out.append(
            SeedCustomer(
                seed_id=f"C{(i + 1):03d}",
                first_name=first,
                last_name="Customer",
                company_name=company,
                salesforce=SalesforcePresence(
                    account_name=company,
                    contact_email=email,
                    status=status,  # type: ignore[arg-type]
                ),
                stripe=StripePresence(
                    customer_email=email,
                    subscription_status=sub_status,  # type: ignore[arg-type]
                    monthly_amount_eur=89 if i % 3 != 0 else 149,
                    last_invoice_date=base - timedelta(days=(i % 28)),
                    invoice_history_months=(i % 6) + 1,
                ),
                hubspot=HubSpotPresence(
                    contact_email=email,
                    in_sequence=sequence,  # type: ignore[arg-type]
                ),
            )
        )
    return out


def _last_friday(d: date) -> date:
    offset = (d.weekday() - 4) % 7
    if offset == 0:
        offset = 7
    return d - timedelta(days=offset)


def build_catalog() -> SeedCatalog:
    base = get_settings().seed_base_date
    discrepancies = _build_discrepancies(base)
    normals = _build_normals(base)
    customers = discrepancies + normals
    return SeedCatalog(customers=customers)

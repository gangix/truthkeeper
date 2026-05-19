"""Pydantic models for the seed catalog.

A SeedCustomer is the abstract identity that appears in some combination of
Salesforce, Stripe, and HubSpot — possibly with deliberately inconsistent
fields across systems (that's what creates a discrepancy).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

DiscrepancyId = Literal[
    "D1_revenue_leak_missed_churn",
    "D2_trial_paid_but_sf_missed",
    "D3_identity_fracture",
    "D4_refunded_but_marketed",
    "D5_orphaned_stripe_customer",
    "NONE",
]


class SalesforcePresence(BaseModel):
    """How this customer should appear in Salesforce, if at all."""

    present: bool = True
    account_name: str
    contact_email: EmailStr
    status: Literal["Trial", "Paid Annual", "Churned", "Prospect"] = "Trial"
    churn_date: date | None = None


class StripePresence(BaseModel):
    """How this customer should appear in Stripe, if at all."""

    present: bool = True
    customer_email: EmailStr
    subscription_status: Literal["active", "canceled", "trialing", "none"] = "active"
    monthly_amount_eur: int = 89
    last_invoice_date: date | None = None
    refunded_last_invoice: bool = False
    invoice_history_months: int = 1  # how many past months to seed


class HubSpotPresence(BaseModel):
    """How this customer should appear in HubSpot, if at all."""

    present: bool = True
    contact_email: EmailStr
    in_sequence: Literal[
        "Engaged Trial",
        "Paying Customer Onboarding",
        "Recent Refunds — Win Back",
        "none",
    ] = "Engaged Trial"


class SeedCustomer(BaseModel):
    """One customer in the seed catalog.

    The same first/last name maps to one logical person. The per-system
    presence objects describe how they appear in each connected SaaS,
    deliberately mismatched if `discrepancy` != NONE.
    """

    seed_id: str = Field(..., description="Stable ID like 'C001'")
    first_name: str
    last_name: str
    company_name: str
    salesforce: SalesforcePresence | None
    stripe: StripePresence | None
    hubspot: HubSpotPresence | None
    discrepancy: DiscrepancyId = "NONE"
    notes: str = ""


class SeedCatalog(BaseModel):
    """The whole catalog of seed customers."""

    customers: list[SeedCustomer]

    def count(self) -> int:
        return len(self.customers)

    def discrepancies(self) -> list[SeedCustomer]:
        return [c for c in self.customers if c.discrepancy != "NONE"]

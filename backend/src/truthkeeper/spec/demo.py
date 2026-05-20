"""Hardcoded CompanyAgentSpec for the seeded demo company.

In Phase 1, the spec is hand-authored. The onboarding flow that auto-discovers
entity mappings + proposes rules lands in Phase 2. The 5 rules below mirror
the verification SQL in `infra/verify_discrepancies.sql` and the 5 demo
discrepancies in PROJECT_BRIEF.md §6.
"""

from __future__ import annotations

from truthkeeper.spec.models import (
    CompanyAgentSpec,
    ConnectedSystem,
    CorrectiveActionTemplate,
    CustomField,
    DomainTerm,
    EntityMapping,
    EntityModel,
    Rule,
    Severity,
    SystemName,
    Vocabulary,
)

_BQ_PROJECT = "truthkeeper-hack-2026"


def _bq(dataset: str, table: str) -> str:
    return f"`{_BQ_PROJECT}.{dataset}.{table}`"


CONNECTED_SYSTEMS: list[ConnectedSystem] = [
    ConnectedSystem(
        name=SystemName.salesforce,
        fivetran_connector_id="path_mantis",
        bigquery_dataset="salesforce",
    ),
    ConnectedSystem(
        name=SystemName.stripe,
        fivetran_connector_id="veteran_intrinsically",
        bigquery_dataset="stripe",
    ),
    ConnectedSystem(
        name=SystemName.hubspot,
        fivetran_connector_id="strung_numerate",
        bigquery_dataset="hubspot",
    ),
]


ENTITY_MODEL: list[EntityModel] = [
    EntityModel(
        name="Customer",
        mappings=[
            EntityMapping(
                system=SystemName.salesforce,
                table="contact",
                id_field="id",
                email_field="email",
                extra_fields={
                    "account_id_field": "account_id",
                    "first_name_field": "first_name",
                    "last_name_field": "last_name",
                    "lifecycle_status_note_field": "description",
                },
            ),
            EntityMapping(
                system=SystemName.stripe,
                table="customer",
                id_field="id",
                email_field="email",
            ),
            EntityMapping(
                system=SystemName.hubspot,
                table="contact",
                id_field="id",
                email_field="property_email",
                extra_fields={
                    "first_name_field": "property_firstname",
                    "last_name_field": "property_lastname",
                    "seed_id_field": "property_tk_seed_id",
                    "current_sequence_field": "property_tk_current_sequence",
                },
            ),
        ],
    ),
    EntityModel(
        name="Account",
        mappings=[
            EntityMapping(
                system=SystemName.salesforce,
                table="account",
                id_field="id",
                extra_fields={
                    "name_field": "name",
                    "lifecycle_status_note_field": "description",
                },
            ),
        ],
    ),
    EntityModel(
        name="Subscription",
        mappings=[
            EntityMapping(
                system=SystemName.stripe,
                table="subscription_history",
                id_field="id",
                status_field="status",
                extra_fields={
                    "customer_id_field": "customer_id",
                    "active_row_filter": "_fivetran_active = TRUE",
                },
            ),
        ],
    ),
    EntityModel(
        name="Invoice",
        mappings=[
            EntityMapping(
                system=SystemName.stripe,
                table="invoice",
                id_field="id",
                status_field="status",
                extra_fields={
                    "customer_id_field": "customer_id",
                    "subscription_id_field": "subscription_id",
                    "amount_field": "total",
                },
            ),
        ],
    ),
    EntityModel(
        name="Charge",
        mappings=[
            EntityMapping(
                system=SystemName.stripe,
                table="charge",
                id_field="id",
                extra_fields={"customer_id_field": "customer_id"},
            ),
        ],
    ),
    EntityModel(
        name="Refund",
        mappings=[
            EntityMapping(
                system=SystemName.stripe,
                table="refund",
                id_field="id",
                status_field="status",
                extra_fields={"charge_id_field": "charge_id"},
            ),
        ],
    ),
]


VOCABULARY = Vocabulary(
    domain_terms=[
        DomainTerm(canonical="Customer", aliases=["Account", "Contact", "Client"]),
        DomainTerm(canonical="Subscription", aliases=["Plan", "Sub"]),
    ],
    status_labels=[
        DomainTerm(canonical="Churned", aliases=["Cancelled", "Lost"]),
        DomainTerm(canonical="Trial", aliases=["Free Trial", "Evaluating"]),
        DomainTerm(canonical="Paid Annual", aliases=["Active", "Annual Customer"]),
    ],
    custom_fields=[
        CustomField(
            system=SystemName.hubspot,
            field="property_tk_seed_id",
            semantic_type="seed_id_marker",
        ),
        CustomField(
            system=SystemName.hubspot,
            field="property_tk_current_sequence",
            semantic_type="marketing_sequence_state",
        ),
    ],
)


D1_SQL = f"""
SELECT
  sf_a.name        AS account_name,
  sf_c.email       AS contact_email,
  s_sub.status     AS stripe_subscription_status,
  s_sub.id         AS stripe_subscription_id,
  s_cust.id        AS stripe_customer_id,
  sf_a.id          AS salesforce_account_id
FROM {_bq("salesforce", "account")} sf_a
JOIN {_bq("salesforce", "contact")} sf_c
  ON sf_c.account_id = sf_a.id
JOIN {_bq("stripe", "customer")} s_cust
  ON LOWER(s_cust.email) = LOWER(sf_c.email)
JOIN {_bq("stripe", "subscription_history")} s_sub
  ON s_sub.customer_id = s_cust.id
 AND s_sub._fivetran_active = TRUE
WHERE sf_a.description LIKE '%[seed:%'
  AND sf_c.description LIKE '%status=Churned%'
  AND s_sub.status IN ('active', 'trialing', 'past_due')
""".strip()


D2_SQL = f"""
SELECT
  sf_c.email       AS contact_email,
  sf_c.description AS sf_status_note,
  sf_c.id          AS salesforce_contact_id,
  s_sub.status     AS stripe_subscription_status,
  s_sub.id         AS stripe_subscription_id,
  s_inv.total      AS last_stripe_invoice_total,
  s_inv.id         AS last_stripe_invoice_id
FROM {_bq("salesforce", "contact")} sf_c
JOIN {_bq("stripe", "customer")} s_cust
  ON LOWER(s_cust.email) = LOWER(sf_c.email)
JOIN {_bq("stripe", "subscription_history")} s_sub
  ON s_sub.customer_id = s_cust.id
 AND s_sub._fivetran_active = TRUE
LEFT JOIN {_bq("stripe", "invoice")} s_inv
  ON s_inv.subscription_id = s_sub.id
WHERE sf_c.description LIKE '%status=Trial%'
  AND s_sub.status = 'active'
""".strip()


D3_SQL = f"""
SELECT
  sf_c.first_name,
  sf_c.last_name,
  sf_c.email           AS sf_email,
  sf_c.id              AS salesforce_contact_id,
  hs_c.property_email  AS hubspot_email,
  hs_c.id              AS hubspot_contact_id
FROM {_bq("salesforce", "contact")} sf_c
JOIN {_bq("hubspot", "contact")} hs_c
  ON LOWER(sf_c.first_name) = LOWER(hs_c.property_firstname)
 AND LOWER(sf_c.last_name)  = LOWER(hs_c.property_lastname)
WHERE LOWER(sf_c.email) != LOWER(hs_c.property_email)
  AND SPLIT(sf_c.email, '@')[OFFSET(1)] = SPLIT(hs_c.property_email, '@')[OFFSET(1)]
""".strip()


D4_SQL = f"""
SELECT
  hs_c.property_email,
  hs_c.property_tk_current_sequence,
  hs_c.id              AS hubspot_contact_id,
  s_cust.id            AS stripe_customer_id,
  s_chg.id             AS stripe_charge_id,
  s_ref.id             AS stripe_refund_id,
  s_ref.created        AS refund_created_at
FROM {_bq("hubspot", "contact")} hs_c
JOIN {_bq("stripe", "customer")} s_cust
  ON LOWER(s_cust.email) = LOWER(hs_c.property_email)
JOIN {_bq("stripe", "charge")} s_chg
  ON s_chg.customer_id = s_cust.id
JOIN {_bq("stripe", "refund")} s_ref
  ON s_ref.charge_id = s_chg.id
WHERE hs_c.property_tk_current_sequence IN ('Paying Customer Onboarding', 'Engaged Trial')
  AND s_ref.status = 'succeeded'
""".strip()


D5_SQL = f"""
SELECT
  s_cust.email,
  s_cust.id                       AS stripe_customer_id,
  hs_c.property_tk_seed_id,
  hs_c.id                         AS hubspot_contact_id,
  COUNT(s_inv.id)                 AS paid_invoice_count
FROM {_bq("stripe", "customer")} s_cust
LEFT JOIN {_bq("stripe", "invoice")} s_inv
  ON s_inv.customer_id = s_cust.id AND s_inv.status = 'paid'
JOIN {_bq("hubspot", "contact")} hs_c
  ON LOWER(hs_c.property_email) = LOWER(s_cust.email)
WHERE hs_c.property_tk_seed_id = 'D005'
GROUP BY s_cust.email, s_cust.id, hs_c.property_tk_seed_id, hs_c.id
""".strip()


RULES: list[Rule] = [
    Rule(
        id="D1",
        name="Active Stripe subscription with Churned Salesforce account",
        description=(
            "A Salesforce Account whose primary Contact is marked Churned still has "
            "an active Stripe subscription. The company is being billed for a "
            "customer who should have stopped paying."
        ),
        severity=Severity.critical,
        sql=D1_SQL,
        reasoning_template=(
            "A revenue-leak disagreement has been detected for {account_name} "
            "(contact {contact_email}). Salesforce marked this account as Churned, "
            "but the corresponding Stripe subscription {stripe_subscription_id} is "
            "still in status '{stripe_subscription_status}'. Most likely cause: a "
            "churn-handling webhook or workflow did not fire, so the subscription "
            "was never cancelled in Stripe. Explain the disagreement in plain "
            "language using the company's vocabulary, estimate the monthly billing "
            "leakage, and present the drafted corrective actions for one-tap "
            "approval."
        ),
        corrective_action_templates=[
            CorrectiveActionTemplate(
                target_system=SystemName.stripe,
                action_type="cancel_subscription",
                parameter_mapping={"subscription_id": "stripe_subscription_id"},
                description="Cancel Stripe subscription {stripe_subscription_id}",
            ),
            CorrectiveActionTemplate(
                target_system=SystemName.salesforce,
                action_type="update_account_status",
                parameter_mapping={
                    "account_id": "salesforce_account_id",
                    "new_status": "Churned",
                },
                description="Confirm Salesforce Account {account_name} status = Churned",
            ),
            CorrectiveActionTemplate(
                target_system=SystemName.hubspot,
                action_type="remove_from_sequence",
                parameter_mapping={
                    "email": "contact_email",
                    "sequence": "Engaged Trial",
                },
                description="Remove {contact_email} from HubSpot 'Engaged Trial' sequence",
            ),
        ],
        monetary_impact_formula="last_stripe_invoice_total_eur",
    ),
    Rule(
        id="D2",
        name="Trial in Salesforce but paid invoice in Stripe",
        description=(
            "A Salesforce Contact is still flagged Trial, but Stripe shows an active "
            "subscription and a recent paid invoice. Sales has lost the upsell signal."
        ),
        severity=Severity.high,
        sql=D2_SQL,
        reasoning_template=(
            "An upsell-missed disagreement: {contact_email} is marked Trial in "
            "Salesforce (note: '{sf_status_note}'), but Stripe shows subscription "
            "{stripe_subscription_id} in status '{stripe_subscription_status}' with "
            "a recent invoice total of {last_stripe_invoice_total} cents. Likely "
            "cause: payment succeeded in Stripe but the Salesforce status update "
            "never propagated. Explain the disagreement in the company's "
            "vocabulary, surface the monetary impact of the missed upsell motion, "
            "and present the drafted corrective actions."
        ),
        corrective_action_templates=[
            CorrectiveActionTemplate(
                target_system=SystemName.salesforce,
                action_type="update_contact_status",
                parameter_mapping={
                    "contact_id": "salesforce_contact_id",
                    "new_status": "Paid Annual",
                },
                description="Update Salesforce Contact {contact_email} status to Paid Annual",
            ),
            CorrectiveActionTemplate(
                target_system=SystemName.salesforce,
                action_type="reassign_owner_to_csm",
                parameter_mapping={"contact_id": "salesforce_contact_id"},
                description="Reassign {contact_email} to Customer Success Manager",
            ),
        ],
        monetary_impact_formula="last_stripe_invoice_total_eur",
    ),
    Rule(
        id="D3",
        name="Identity fracture across Salesforce and HubSpot",
        description=(
            "The same person exists as two distinct contacts under different email "
            "aliases of the same domain in Salesforce and HubSpot. Attribution and "
            "communication get split across the two records."
        ),
        severity=Severity.medium,
        sql=D3_SQL,
        reasoning_template=(
            "An identity-fracture disagreement: {first_name} {last_name} appears in "
            "Salesforce as '{sf_email}' but in HubSpot as '{hubspot_email}' — same "
            "human, two records, same domain. Likely cause: the contact was created "
            "independently in each system without an email-canonicalization rule. "
            "Explain the disagreement, describe the downstream attribution risk, "
            "and present the drafted merge action."
        ),
        corrective_action_templates=[
            CorrectiveActionTemplate(
                target_system=SystemName.hubspot,
                action_type="merge_contacts",
                parameter_mapping={
                    "primary_email": "sf_email",
                    "duplicate_contact_id": "hubspot_contact_id",
                },
                description=(
                    "Merge HubSpot contact {hubspot_email} into the canonical "
                    "Salesforce email {sf_email}"
                ),
            ),
        ],
        monetary_impact_formula=None,
    ),
    Rule(
        id="D4",
        name="Refunded in Stripe but still in active onboarding sequence",
        description=(
            "A Stripe refund has succeeded, but HubSpot is still marketing the "
            "customer through an active onboarding or trial sequence. Customer "
            "experience risk."
        ),
        severity=Severity.high,
        sql=D4_SQL,
        reasoning_template=(
            "A customer-experience disagreement: {property_email} was refunded in "
            "Stripe (refund {stripe_refund_id}, succeeded on {refund_created_at}) "
            "but is still enrolled in HubSpot sequence "
            "'{property_tk_current_sequence}'. Likely cause: Stripe refund did not "
            "trigger removal from the HubSpot marketing automation. Explain the "
            "disagreement, frame the customer-trust risk, and present the drafted "
            "sequence-swap actions."
        ),
        corrective_action_templates=[
            CorrectiveActionTemplate(
                target_system=SystemName.hubspot,
                action_type="remove_from_sequence",
                parameter_mapping={
                    "email": "property_email",
                    "sequence": "property_tk_current_sequence",
                },
                description=(
                    "Remove {property_email} from HubSpot sequence "
                    "'{property_tk_current_sequence}'"
                ),
            ),
            CorrectiveActionTemplate(
                target_system=SystemName.hubspot,
                action_type="add_to_sequence",
                parameter_mapping={
                    "email": "property_email",
                    "sequence": "Recent Refunds — Win Back",
                },
                description=(
                    "Add {property_email} to HubSpot 'Recent Refunds — Win Back' sequence"
                ),
            ),
        ],
        monetary_impact_formula=None,
    ),
    Rule(
        id="D5",
        name="Orphaned Stripe customer not present in Salesforce",
        description=(
            "A Stripe customer with paid invoices exists in HubSpot but never made "
            "it into Salesforce — sales has no record. Almost always a silent "
            "webhook failure."
        ),
        severity=Severity.critical,
        sql=D5_SQL,
        reasoning_template=(
            "A silent-integration-failure disagreement: {email} exists in Stripe "
            "(customer {stripe_customer_id}) with {paid_invoice_count} paid "
            "invoices and is tracked in HubSpot under seed marker "
            "'{property_tk_seed_id}', but has no Salesforce record. Likely cause: "
            "the Stripe→Salesforce account-creation webhook failed silently at "
            "signup. Explain the disagreement, frame the revenue-attribution risk, "
            "and present the drafted Salesforce Account creation action."
        ),
        corrective_action_templates=[
            CorrectiveActionTemplate(
                target_system=SystemName.salesforce,
                action_type="create_account_from_stripe_customer",
                parameter_mapping={
                    "stripe_customer_id": "stripe_customer_id",
                    "email": "email",
                },
                description="Create Salesforce Account for Stripe customer {email}",
            ),
        ],
        monetary_impact_formula="sum_paid_invoice_total_eur",
    ),
]


DEMO_SPEC = CompanyAgentSpec(
    company_id="truthkeeper-demo",
    company_name="TruthKeeper Demo Co",
    connected_systems=CONNECTED_SYSTEMS,
    entity_model=ENTITY_MODEL,
    rules=RULES,
    vocabulary=VOCABULARY,
    tool_parameters={
        SystemName.salesforce: {"instance_url_env_var": "SALESFORCE_INSTANCE_URL"},
        SystemName.stripe: {"api_key_env_var": "STRIPE_SECRET_KEY"},
        SystemName.hubspot: {"access_token_env_var": "HUBSPOT_ACCESS_TOKEN"},
    },
    domain_context=(
        "TruthKeeper Demo Co is a fictional B2B SaaS with ~50 customers across "
        "Salesforce, Stripe, and HubSpot. Customers move through lifecycle stages "
        "Trial → Paid Annual → Churned. The seed catalog deliberately introduces "
        "five cross-system disagreements (D1–D5) that the agent should detect, "
        "explain, and propose corrective actions for. Use the customer's lifecycle "
        "vocabulary (Churned, Trial, Paid Annual) when explaining violations."
    ),
)

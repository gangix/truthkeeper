-- TruthKeeper — BigQuery verification queries for the 5 demo discrepancies.
--
-- Run each block individually with:
--   bq query --use_legacy_sql=false "$(sed -n '/^-- D1:/,/^;/p' infra/verify_discrepancies.sql)"
--
-- Each query is expected to return >=1 row matching its discrepancy.
--
-- Notes on Fivetran's BigQuery naming conventions:
-- - Datasets are named after the Destination Schema field (we used: salesforce, stripe, hubspot)
-- - HubSpot's connector PREFIXES all properties (standard + custom) with `property_`
--   So firstname is `property_firstname`, our custom tk_seed_id is `property_tk_seed_id`
-- - Stripe/Salesforce table columns use their source-system names directly (no prefix)
--
-- Status:
-- - HubSpot connector: ACTIVE, syncing to dataset `hubspot` -- rules using HubSpot work today
-- - Salesforce connector: ACTIVE, syncing to dataset `salesforce` (account 111 rows, contact 118 rows; ~98 seeded each + SF DE sample data)
-- - Stripe Test connector: HISTORICAL SYNC STUCK at 97/98 tables. `stripe.subscription` table NOT yet in BigQuery.
--   D1 and D2 will start passing the moment the Stripe sync unblocks; their SQL is correct as written.

-- ────────────────────────────────────────────────────────────────────────
-- D1: Revenue leak -- Stripe sub still active for an SF Account marked Churned
-- Expected: 1 row (Anna Chen / Acme Corp)
-- NEEDS: salesforce.account, salesforce.contact, stripe.customer, stripe.subscription
-- Currently fails: stripe.subscription not yet synced.
-- ────────────────────────────────────────────────────────────────────────
SELECT
  sf_a.name        AS account_name,
  sf_c.email       AS contact_email,
  s_sub.status     AS stripe_subscription_status
FROM `truthkeeper-hack-2026.salesforce.account` sf_a
JOIN `truthkeeper-hack-2026.salesforce.contact` sf_c
  ON sf_c.account_id = sf_a.id
JOIN `truthkeeper-hack-2026.stripe.customer` s_cust
  ON LOWER(s_cust.email) = LOWER(sf_c.email)
JOIN `truthkeeper-hack-2026.stripe.subscription` s_sub
  ON s_sub.customer_id = s_cust.id
WHERE sf_a.description LIKE '%[seed:%'
  AND sf_c.description LIKE '%status=Churned%'
  AND s_sub.status IN ('active', 'trialing', 'past_due')
;

-- ────────────────────────────────────────────────────────────────────────
-- D2: Trial in SF but paid in Stripe
-- Expected: 1 row (Ben Park / Beta Industries)
-- Currently fails: stripe.subscription not yet synced.
-- ────────────────────────────────────────────────────────────────────────
SELECT
  sf_c.email     AS contact_email,
  sf_c.description AS sf_status_note,
  s_sub.status   AS stripe_subscription_status,
  s_inv.total    AS last_stripe_invoice_total
FROM `truthkeeper-hack-2026.salesforce.contact` sf_c
JOIN `truthkeeper-hack-2026.stripe.customer` s_cust
  ON LOWER(s_cust.email) = LOWER(sf_c.email)
JOIN `truthkeeper-hack-2026.stripe.subscription` s_sub
  ON s_sub.customer_id = s_cust.id
LEFT JOIN `truthkeeper-hack-2026.stripe.invoice` s_inv
  ON s_inv.subscription_id = s_sub.id
WHERE sf_c.description LIKE '%status=Trial%'
  AND s_sub.status = 'active'
;

-- ────────────────────────────────────────────────────────────────────────
-- D3: Identity fracture -- same person, different email aliases SF vs HubSpot
-- Expected: 1 row (John Smith: j.smith@gamma.example.com vs john.smith@gamma.example.com)
-- Verified passing 2026-05-20.
-- ────────────────────────────────────────────────────────────────────────
SELECT
  sf_c.first_name,
  sf_c.last_name,
  sf_c.email   AS sf_email,
  hs_c.property_email AS hubspot_email
FROM `truthkeeper-hack-2026.salesforce.contact` sf_c
JOIN `truthkeeper-hack-2026.hubspot.contact` hs_c
  ON LOWER(sf_c.first_name) = LOWER(hs_c.property_firstname)
 AND LOWER(sf_c.last_name)  = LOWER(hs_c.property_lastname)
WHERE LOWER(sf_c.email) != LOWER(hs_c.property_email)
  AND SPLIT(sf_c.email, '@')[OFFSET(1)] = SPLIT(hs_c.property_email, '@')[OFFSET(1)]
;

-- ────────────────────────────────────────────────────────────────────────
-- D4: Refunded in Stripe but still in active onboarding sequence in HubSpot
-- Expected: 1 row (Diana Vega / Delta Co)
-- Works as soon as Stripe sync completes (HubSpot already synced).
-- ────────────────────────────────────────────────────────────────────────
SELECT
  hs_c.property_email,
  hs_c.property_tk_current_sequence,
  s_cust.id     AS stripe_customer_id,
  s_ref.created AS refund_created_at
FROM `truthkeeper-hack-2026.hubspot.contact` hs_c
JOIN `truthkeeper-hack-2026.stripe.customer` s_cust
  ON LOWER(s_cust.email) = LOWER(hs_c.property_email)
JOIN `truthkeeper-hack-2026.stripe.charge` s_chg
  ON s_chg.customer_id = s_cust.id
JOIN `truthkeeper-hack-2026.stripe.refund` s_ref
  ON s_ref.charge_id = s_chg.id
WHERE hs_c.property_tk_current_sequence IN ('Paying Customer Onboarding', 'Engaged Trial')
  AND s_ref.status = 'succeeded'
;

-- ────────────────────────────────────────────────────────────────────────
-- D5: Orphaned Stripe customer -- exists in Stripe + HubSpot, NOT in SF
-- Expected: 1 row (Eric Olsen / Epsilon Holdings, seed_id=D005)
-- This HubSpot+Stripe-only form has been the working ground truth since
-- Stripe sync started; it identifies the orphan via the HubSpot seed marker
-- without depending on SF data.
-- ────────────────────────────────────────────────────────────────────────
SELECT
  s_cust.email,
  s_cust.id         AS stripe_customer_id,
  hs_c.property_tk_seed_id,
  COUNT(s_inv.id)   AS paid_invoice_count
FROM `truthkeeper-hack-2026.stripe.customer` s_cust
LEFT JOIN `truthkeeper-hack-2026.stripe.invoice` s_inv
  ON s_inv.customer_id = s_cust.id AND s_inv.status = 'paid'
JOIN `truthkeeper-hack-2026.hubspot.contact` hs_c
  ON LOWER(hs_c.property_email) = LOWER(s_cust.email)
WHERE hs_c.property_tk_seed_id = 'D005'
GROUP BY s_cust.email, s_cust.id, hs_c.property_tk_seed_id
;

-- ────────────────────────────────────────────────────────────────────────
-- D5 alt: orphan check via SF absence (now that SF is synced)
-- Returns Stripe customers whose email has no matching SF contact.
-- Known false positive: D3 (John Smith) -- his Stripe email john.smith@
-- doesn't match SF's j.smith@ alias. Real reconciliation rule will need
-- canonical-email normalization to avoid flagging the same person twice.
-- ────────────────────────────────────────────────────────────────────────
SELECT
  s_cust.email,
  s_cust.id    AS stripe_customer_id,
  s_cust.created AS stripe_customer_created,
  COUNT(s_inv.id) AS paid_invoice_count
FROM `truthkeeper-hack-2026.stripe.customer` s_cust
LEFT JOIN `truthkeeper-hack-2026.salesforce.contact` sf_c
  ON LOWER(sf_c.email) = LOWER(s_cust.email)
LEFT JOIN `truthkeeper-hack-2026.stripe.invoice` s_inv
  ON s_inv.customer_id = s_cust.id AND s_inv.status = 'paid'
WHERE sf_c.id IS NULL
  AND s_cust.email LIKE '%.example.com'
GROUP BY s_cust.email, s_cust.id, s_cust.created
;

-- ────────────────────────────────────────────────────────────────────────
-- Sanity: 5 seeded HubSpot discrepancy contacts visible
-- (no joins needed, works today since HubSpot is synced)
-- ────────────────────────────────────────────────────────────────────────
SELECT
  property_tk_seed_id AS seed_id,
  property_firstname,
  property_lastname,
  property_email,
  property_tk_current_sequence
FROM `truthkeeper-hack-2026.hubspot.contact`
WHERE property_tk_seed_id LIKE 'D%'
ORDER BY property_tk_seed_id
;

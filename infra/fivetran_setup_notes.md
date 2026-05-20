# Fivetran dashboard setup — human checklist

One BigQuery destination + three source connectors (Salesforce, Stripe, HubSpot).
All steps run in the Fivetran dashboard (https://fivetran.com/dashboard). No code.

## 1. Destination: BigQuery

1. Dashboard → Destinations → **+ Add destination**
2. Pick **BigQuery**
3. Destination name: `truthkeeper_bq`
4. Project ID: `truthkeeper-hack-2026`
5. Dataset location: `EU`
6. Authentication: **Service account key** — paste contents of `~/.config/truthkeeper/fivetran-bq-writer.json` (created by `infra/bigquery_setup.sh`)
7. **No destination-schema prefix.** Each connector's schema name lands as a top-level BigQuery dataset (`salesforce`, `stripe`, `hubspot`) — not `truthkeeper_salesforce` as the original plan draft suggested. The `verify_discrepancies.sql` queries assume the unprefixed form.
8. Save and test → should report "Connected".

## 2. Source: Salesforce

### 2a. Salesforce-side prerequisite (Agentforce trial orgs only)

Agentforce trial orgs and some Developer Edition orgs ship without the **"Approve Uninstalled Connected Apps"** system permission on the System Administrator profile. Without it, the OAuth grant fails with `end-user denied authorization` even after the user clicks Allow on the consent screen — Salesforce blocks creation of the auto-managed Connected App entry for Fivetran.

Fix via a Permission Set (one-time):

1. SF Setup → **Permission Sets** → **New**
2. Label: `Fivetran OAuth Authorize` · API Name: `Fivetran_OAuth_Authorize` · License: `--None--`
3. Save → open **System Permissions** → **Edit**
4. Check **Approve Uninstalled Connected Apps** → Save
5. **Manage Assignments** → **Add Assignment** → pick your user → **Assign**
6. Wait ~30 s for permission cache, then retry the Fivetran Authorize step

### 2b. Fivetran-side configuration

1. Connectors → **+ Add connector** → **Salesforce** (plain — not Sandbox, not Marketing Cloud, not Pardot)
2. Destination: `truthkeeper_bq`
3. Destination schema: `salesforce`
4. Destination schema names: **Fivetran naming** (lowercase + snake_case — what `verify_discrepancies.sql` assumes; also matches the existing Stripe/HubSpot connectors). **Locks at first sync, get it right now.**
5. Connection Method: **Connect directly**
6. Sync formula fields: **off** (Fivetran flags as data-integrity-risky)
7. Sync Salesforce Files: **off**
8. Max Salesforce API usage: leave at default (90%)
9. **Authentication** → click **Authorize** → SF login → on consent screen click **Allow** → ✓ Authorized
10. **Save & Test** → Connected
11. Schema config → keep Account + Contact enabled (default). Other tables can be left on; they're empty in the DE org and cost nothing in BQ.
12. Change handling: **Allow columns** (new columns on existing tables sync automatically; new tables stay blocked)
13. Sync starts.

## 3. Source: Stripe

1. Connectors → **+ Add connector** → **Stripe**
2. Connector name: `stripe_test`
3. Destination: `truthkeeper_bq`
4. Destination schema: `stripe`
5. Auth: paste your `sk_test_...` secret key
6. Tables (minimum for demo): `customer`, `subscription`, `invoice`, `refund`, `charge`
7. Schedule: every 15 minutes
8. Initial sync starts

> **Known issue (2026-05-20):** the historical sync has been stuck at 97/98 tables for several hours; `stripe.subscription` has not yet landed. Discrepancies D1 and D2 require this table — they'll start passing the moment Stripe completes. Investigate via Fivetran connector logs.

## 4. Source: HubSpot

1. Connectors → **+ Add connector** → **HubSpot**
2. Connector name: `hubspot_dev`
3. Destination: `truthkeeper_bq`
4. Destination schema: `hubspot`
5. Auth: OAuth → sign into developer test account
6. Tables: `Contact`, `Company`
7. **Custom properties (CRITICAL):** in the connector's table-config screen for Contact, enable sync for the custom properties `tk_seed_id` and `tk_current_sequence`. Without this, several discrepancy rules can't see the encoded state.
8. Schedule: every 15 minutes
9. Initial sync starts

## 5. Verify in BigQuery

```bash
bq --project_id=truthkeeper-hack-2026 ls --format=pretty
# Expected datasets: salesforce, stripe, hubspot, truthkeeper_demo, fivetran_*_staging

for schema in salesforce stripe hubspot; do
  echo "=== $schema ==="
  bq --project_id=truthkeeper-hack-2026 ls "$schema" | head
done
```

Then run `infra/verify_discrepancies.sql` — see header notes for current pass/fail status per rule.

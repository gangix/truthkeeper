# seed/

Deterministic seed data for the TruthKeeper demo.

## What it does

Populates three SaaS sandboxes (Salesforce Developer Edition, Stripe test
mode, HubSpot Developer) with 50 customers — 45 consistent across all
three systems, 5 with deliberate cross-system disagreements that map to
the brief's §6 demo discrepancies.

## Setup

```bash
cp .env.example .env
# Fill in real credentials (see PROJECT_BRIEF.md for what each value means)
uv sync
```

**HubSpot one-time setup** (must happen once before first run): create
two custom contact properties via HubSpot UI:
- Internal name `tk_seed_id`, type Single-line text
- Internal name `tk_current_sequence`, type Single-line text

## Run

```bash
uv run seed
```

Outputs per-system progress. Safe to run multiple times — upserts
idempotently.

## Reset

```bash
uv run seed-teardown
```

Deletes records matching our seed tags from each system. Stripe teardown
refuses to run unless `STRIPE_SECRET_KEY` starts with `sk_test_`.

## Test (no live credentials needed)

```bash
uv run pytest
```

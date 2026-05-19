# infra/

Provisioning scripts for the cloud resources TruthKeeper depends on.

## bigquery_setup.sh

Creates (idempotently):
- BigQuery dataset `truthkeeper_demo` in EU
- Service account `fivetran-bq-writer@<project>.iam.gserviceaccount.com`
- Grants `roles/bigquery.dataEditor` and `roles/bigquery.jobUser`
- Generates a JSON key at `~/.config/truthkeeper/fivetran-bq-writer.json`

Run with:

```bash
GCP_PROJECT_ID=truthkeeper-hack-2026 ./infra/bigquery_setup.sh
```

The JSON key is what you paste into the Fivetran dashboard when configuring
the BigQuery destination. It is NOT committed to the repo (lives under
`~/.config/`).

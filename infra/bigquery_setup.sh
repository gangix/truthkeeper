#!/usr/bin/env bash
# Idempotent BigQuery setup for TruthKeeper. Safe to run multiple times.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-truthkeeper-hack-2026}"
DATASET="${BQ_DATASET:-truthkeeper_demo}"
LOCATION="${BQ_LOCATION:-EU}"
SA_NAME="fivetran-bq-writer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="${HOME}/.config/truthkeeper/fivetran-bq-writer.json"

echo "== Enabling BigQuery + IAM APIs =="
gcloud services enable bigquery.googleapis.com iam.googleapis.com --project="${PROJECT_ID}"

echo "== Creating dataset ${PROJECT_ID}:${DATASET} (location=${LOCATION}) =="
if bq --project_id="${PROJECT_ID}" ls --datasets 2>/dev/null | grep -qw "${DATASET}"; then
  echo "Dataset already exists"
else
  bq --project_id="${PROJECT_ID}" --location="${LOCATION}" mk --dataset \
    --description="TruthKeeper Fivetran sync destination" "${DATASET}"
fi

echo "== Creating service account ${SA_NAME} =="
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Service account already exists"
else
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Fivetran BigQuery writer for TruthKeeper" \
    --project="${PROJECT_ID}"
fi

echo "== Granting BigQuery roles to ${SA_EMAIL} =="
for role in roles/bigquery.dataEditor roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --condition=None \
    --quiet >/dev/null
done

echo "== Generating service account key (saved to ${KEY_FILE}) =="
mkdir -p "$(dirname "${KEY_FILE}")"
if [[ -f "${KEY_FILE}" ]]; then
  echo "Key file already exists at ${KEY_FILE} -- keeping existing key"
else
  gcloud iam service-accounts keys create "${KEY_FILE}" \
    --iam-account="${SA_EMAIL}" \
    --project="${PROJECT_ID}"
fi

echo ""
echo "=========================================================="
echo "Done. Use these values when configuring Fivetran BigQuery"
echo "destination in the dashboard:"
echo ""
echo "  Project ID:    ${PROJECT_ID}"
echo "  Dataset:       ${DATASET}"
echo "  Location:      ${LOCATION}"
echo "  Service acct:  ${SA_EMAIL}"
echo "  JSON key file: ${KEY_FILE}"
echo "=========================================================="

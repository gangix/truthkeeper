# backend/

FastAPI service for TruthKeeper. Deploys to Cloud Run.

## Run locally

```bash
uv run uvicorn truthkeeper.main:app --port 8080 --reload
```

## Test

```bash
uv run pytest
```

## Deploy

```bash
gcloud run deploy truthkeeper-backend \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated
```

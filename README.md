# TruthKeeper

> Your stack is lying to itself.

An autonomous cross-system reconciliation agent for B2B operations. TruthKeeper continuously compares what your SaaS systems (Salesforce, Stripe, HubSpot, …) believe about your customers, revenue, and operations; finds the disagreements that cost money; explains how each happened; and drafts the cross-system corrective actions for one-tap approval.

Built for the [Building Agents for Real-World Challenges](https://buildwithai.devpost.com/) hackathon — Fivetran track.

**Status:** in development. Submission deadline 2026-06-11.

## Stack

- **Agent:** Google Agent Development Kit (ADK) + Gemini 3.1 Pro via Vertex AI
- **Partner integration:** Fivetran's official MCP server (stdio) via ADK `StdioConnectionParams`
- **Data ingestion:** Fivetran → BigQuery
- **Backend:** Python 3.13 / FastAPI on Cloud Run
- **Frontend:** Next.js 15 / Tailwind / shadcn/ui on Vercel
- **State:** Postgres on Neon

## Repo layout

| Path | Purpose |
|------|---------|
| `validation/` | Throwaway scripts that prove the partner integration |
| `backend/` | FastAPI + agent orchestration |
| `frontend/` | Next.js UI |

## Hosted demo

- **Frontend (live):** https://truthkeeper-portal.vercel.app
- **Backend health:** https://truthkeeper-backend-928905928787.europe-west1.run.app/health

The frontend is currently a hello-world scaffold that pings the backend's `/health` endpoint. The full onboarding wizard and disagreement feed land in Plans 4-5.

## Day 1 status

End of Plan 1 (Foundation):

- ✅ Critical-path validation: Gemini 3.1 Pro → ADK → stdio → Fivetran's official MCP server → real Fivetran data → coherent natural-language synthesis. See `validation/hello_mcp.py`.
- ✅ Backend (FastAPI) deployed to Cloud Run, `/health` returning `{"status":"ok"}`.
- ✅ Frontend (Next.js 15 + shadcn/ui) deployed to Vercel, pinging backend successfully.

## License

MIT — see [LICENSE](LICENSE).


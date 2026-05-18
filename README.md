# TruthKeeper

> Your stack is lying to itself.

An autonomous cross-system reconciliation agent for B2B operations. TruthKeeper continuously compares what your SaaS systems (Salesforce, Stripe, HubSpot, …) believe about your customers, revenue, and operations; finds the disagreements that cost money; explains how each happened; and drafts the cross-system corrective actions for one-tap approval.

Built for the [Building Agents for Real-World Challenges](https://buildwithai.devpost.com/) hackathon — Fivetran track.

**Status:** in development. Submission deadline 2026-06-11.

## Stack

- **Agent:** Google Agent Development Kit (ADK) + Gemini 3.1 Pro via Vertex AI
- **Partner integration:** Fivetran's official MCP server (stdio) via ADK `StdioConnectionParams`
- **Data ingestion:** Fivetran → BigQuery
- **Backend:** Python 3.11 / FastAPI on Cloud Run
- **Frontend:** Next.js 15 / Tailwind / shadcn/ui on Vercel
- **State:** Postgres on Neon

## Repo layout

| Path | Purpose |
|------|---------|
| `PROJECT_BRIEF.md` | Original project brief (authoritative for unchanged sections) |
| `docs/superpowers/specs/` | Design specs |
| `docs/superpowers/plans/` | Implementation plans |
| `validation/` | Throwaway scripts that prove integrations |
| `backend/` | FastAPI + agent orchestration |
| `frontend/` | Next.js UI |

## Hosted demo

(Link added at submission time.)

## License

MIT — see [LICENSE](LICENSE).

---

*Originally drafted under the name Concordance — see commit history.*

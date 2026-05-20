"""ADK SequentialAgent with three sub-agents: Discovery, Profiling, Synthesis.

Discovery uses Fivetran MCP tools (no output_schema, free-form output written
to session_state). Profiling uses the bigquery_profile FunctionTool. Synthesis
has output_schema=OnboardingProposal and no tools (ADK 1.x constraint:
output_schema and tools are mutually exclusive on one agent — see
reasoning/agent.py:8).
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent, SequentialAgent

from truthkeeper.onboarding.bigquery_profile import bigquery_profile_tool
from truthkeeper.onboarding.mcp_tools import build_fivetran_toolset
from truthkeeper.onboarding.proposal import OnboardingProposal

_FALLBACK_MODEL = "gemini-3.1-pro-preview"


def _resolve_model_id() -> str:
    return os.environ.get("GEMINI_MODEL_ID", _FALLBACK_MODEL)


_DISCOVERY_INSTRUCTION = """\
You are the Discovery sub-agent for TruthKeeper onboarding.

Goal: enumerate the company's connected SaaS systems and the tables / columns each one exposes via Fivetran.

Procedure:
1. Call `list_connectors` (or `list_connections` — use whichever the toolset surfaces).
2. For EACH discovered connector, call `get_connector_schemas` (or equivalent) to get its tables and columns.
3. Once all schema data is collected, respond with a single concise paragraph summarizing what you found. Mention each connector by id and the most relevant tables.

Do not invent connector ids. Do not skip the per-connector schema calls. The next sub-agent depends on the full inventory being on the record.
"""


_PROFILING_INSTRUCTION = """\
You are the Profiling sub-agent for TruthKeeper onboarding.

Read the prior Discovery sub-agent's findings (the conversation history above).

Goal: for each discovered table, pick categorical-looking string columns (column type is STRING/VARCHAR, name does NOT end in `_id`, `_at`, `_email`, and is not obviously a free-text field like `description`) and call the `profile_columns` tool to learn their distinct values and counts.

Procedure:
1. For each discovered table, choose up to 5 categorical-looking columns.
2. Call `profile_columns(dataset=..., table=..., columns=[...])` per table — one call per table, NOT per column.
3. After all profiling calls, respond with a single paragraph summarizing what you learned (e.g. "salesforce.account.status has 3 distinct values: Active, Trial, Churned"). This summary is the input to Synthesis.

Skip tables you cannot profile. Do not call the tool more than once per (dataset, table).
"""


_SYNTHESIS_INSTRUCTION = """\
You are the Synthesis sub-agent for TruthKeeper onboarding.

Read both the Discovery summary and the Profiling summary from the conversation history above.

Produce an OnboardingProposal JSON with:
- `proposal_id`: a stable unique string like "prop-<8-char-hex>". Pick any.
- `entities`: ProposedEntity rows that map unified concepts (Customer, Subscription, Invoice, Contact, Deal) to the discovered tables across systems. Use `proposal_id` like "ent-customer", "ent-subscription". Include at least Customer mapping to salesforce.account + stripe.customer + hubspot.company if those tables were found.
- `rules`: ProposedRule rows mirroring the 5 hand-coded rules in the existing DEMO_SPEC (D1 active-sub-on-churned-account, D2 paid-but-still-trial, D3 identity-fracture, D4 refunded-still-marketed, D5 orphaned-stripe). Use `proposal_id` like "rule-d1".
- `vocabulary`: ProposedVocabularyTerm rows for the canonical values you saw in profiling — e.g. canonical "Active", aliases the system-specific labels that mean Active.
- `source_run_id`: the ADK invocation id from session metadata if available, else "run-anon".

Output MUST be valid OnboardingProposal JSON. No prose. No tool calls (you have none).
"""


def build_onboarding_pipeline(*, model: str | None = None) -> SequentialAgent:
    resolved_model = model or _resolve_model_id()

    discovery = LlmAgent(
        name="DiscoveryAgent",
        model=resolved_model,
        description="Discovers connectors + schemas via Fivetran MCP.",
        instruction=_DISCOVERY_INSTRUCTION,
        tools=[build_fivetran_toolset()],
        output_key="discovery_summary",
    )

    profiling = LlmAgent(
        name="ProfilingAgent",
        model=resolved_model,
        description="Profiles categorical columns via BigQuery.",
        instruction=_PROFILING_INSTRUCTION,
        tools=[bigquery_profile_tool],
        output_key="profiling_summary",
    )

    synthesis = LlmAgent(
        name="SynthesisAgent",
        model=resolved_model,
        description="Emits an OnboardingProposal from discovery + profiling summaries.",
        instruction=_SYNTHESIS_INSTRUCTION,
        output_schema=OnboardingProposal,
    )

    return SequentialAgent(
        name="onboarding_pipeline",
        sub_agents=[discovery, profiling, synthesis],
    )

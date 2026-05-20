"""ADK SequentialAgent with three sub-agents: Discovery, Profiling, Synthesis.

Discovery uses Fivetran MCP tools (no output_schema, free-form output written
to session_state). Profiling uses the bigquery_profile FunctionTool. Synthesis
has output_schema=OnboardingProposal and no tools (ADK 1.x constraint:
output_schema and tools are mutually exclusive on one agent — see
reasoning/agent.py:8).
"""

from __future__ import annotations

import json
import os

from google.adk.agents import LlmAgent, SequentialAgent

from truthkeeper.onboarding.bigquery_profile import bigquery_profile_tool
from truthkeeper.onboarding.mcp_tools import build_fivetran_toolset
from truthkeeper.onboarding.proposal import OnboardingProposal
from truthkeeper.spec.demo import DEMO_SPEC

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


def _build_synthesis_instruction() -> str:
    """Build the SynthesisAgent instruction with DEMO_SPEC's rule SQL pinned in.

    The agent invents entities + vocabulary from its discovery/profiling, but
    rule SQL strings are taken verbatim from DEMO_SPEC. This prevents Gemini
    from guessing column names (Fivetran sync uses snake_case; the agent
    occasionally guesses PascalCase) and producing rules that fire 0
    violations at reconcile time.
    """
    pinned_rules = []
    for r in DEMO_SPEC.rules:
        pinned_rules.append(
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "severity": r.severity.value,
                "sql": r.sql,
                "reasoning_template": r.reasoning_template,
                "corrective_action_templates": [
                    {
                        "target_system": t.target_system.value,
                        "action_type": t.action_type,
                        "parameter_mapping": t.parameter_mapping,
                        "description": t.description,
                    }
                    for t in r.corrective_action_templates
                ],
                "monetary_impact_formula": r.monetary_impact_formula,
            }
        )
    pinned_rules_json = json.dumps(pinned_rules, indent=2)
    # DEMO_SPEC.rules.reasoning_template contains literal `{column_name}` style
    # placeholders that are resolved at reconcile time, not by ADK's instruction
    # templating. Double the braces so ADK's format() pass treats them as
    # literal characters; the doubled braces collapse back to single in the
    # final prompt the LLM sees, and Gemini emits them unchanged into the
    # proposal's reasoning_template field — where reconcile expects them.
    pinned_rules_json = pinned_rules_json.replace("{", "{{").replace("}", "}}")

    return f"""\
You are the Synthesis sub-agent for TruthKeeper onboarding.

Read both the Discovery summary and the Profiling summary from the conversation history above.

Produce an OnboardingProposal JSON with these fields:

- `proposal_id`: a stable unique string like "prop-<8-char-hex>". Pick any.

- `entities`: ProposedEntity rows that map unified concepts (Customer, Subscription, Invoice, Contact, Deal) to the discovered tables across systems. Use `proposal_id` like "ent-customer", "ent-subscription". Include at least Customer mapping to salesforce.account + stripe.customer + hubspot.company if those tables were found.

- `rules`: PINNED. Use the rule list below VERBATIM — copy each rule's `sql`, `reasoning_template`, `corrective_action_templates`, and `monetary_impact_formula` exactly as given. Set each rule's `proposal_id` to "rule-" plus the rule id (e.g. "rule-D1"). Do NOT invent new SQL; do NOT modify the SQL. These SQL strings have been validated against the actual Fivetran-synced BigQuery schema.

Pinned rules JSON (use verbatim — only set `proposal_id`):

{pinned_rules_json}

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
        instruction=_build_synthesis_instruction(),
        output_schema=OnboardingProposal,
    )

    return SequentialAgent(
        name="onboarding_pipeline",
        sub_agents=[discovery, profiling, synthesis],
    )

"""ADK LlmAgent wrapper: per-violation reasoning powered by Gemini 3.

For the first reasoning loop we run a single-turn LlmAgent with `output_schema`
set, which forces Gemini to emit JSON matching `ReasoningOutput`. Tools are
deliberately omitted on this path — structured output and tool use are
mutually exclusive in ADK 1.x, and per-violation reasoning doesn't need
tool calls. Fivetran MCP attachment lives on a follow-up multi-step agent
when we want sync-freshness checks.
"""

from __future__ import annotations

import json
import re
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from truthkeeper.reasoning.output import ReasoningOutput
from truthkeeper.spec.models import CompanyAgentSpec, EntityModel, Rule

_DEFAULT_MODEL = "gemini-3.1-pro-preview"
_APP_NAME = "truthkeeper-reconcile"
_USER_ID = "agent"


def _relevant_entities(rule: Rule, spec: CompanyAgentSpec) -> list[EntityModel]:
    sql_lower = rule.sql.lower()
    out: list[EntityModel] = []
    for em in spec.entity_model:
        for mapping in em.mappings:
            if mapping.table.lower() in sql_lower:
                out.append(em)
                break
    return out


_STATIC_INSTRUCTION = (
    "You are TruthKeeper, a cross-system reconciliation agent. "
    "For each violation, produce a ReasoningOutput JSON object that explains the "
    "disagreement in plain language using the company's vocabulary, names the most "
    "likely root cause, estimates monetary impact when applicable, and drafts the "
    "cross-system corrective actions a human can approve.\n\n"
    "Rules for drafted_actions:\n"
    "  * For each corrective action template, emit one DraftedAction.\n"
    "  * The `parameters` field MUST be populated. Take the action template's "
    "`parameter_mapping`: each key is the parameter name, each value is either "
    "a column name in the violation row or a literal value. Resolve each entry "
    "to its actual value (looking it up in the violation row if it matches a "
    "column name; otherwise pass the literal through unchanged). Never return "
    "an empty `parameters` dict.\n"
    "  * The `description` field MUST be a concrete human preview with the "
    "actual values substituted in (not column names).\n\n"
    "Worked example: if a corrective action template has "
    'parameter_mapping={"subscription_id": "stripe_subscription_id", '
    '"reason": "Salesforce marked Churned"} and the violation row has '
    'stripe_subscription_id="sub_ABC", then the DraftedAction must be '
    '{"target_system": "stripe", "action_type": "cancel_subscription", '
    '"parameters": {"subscription_id": "sub_ABC", '
    '"reason": "Salesforce marked Churned"}, '
    '"description": "Cancel Stripe subscription sub_ABC"}.'
)


def _build_user_message(
    rule: Rule, violation: dict[str, Any], spec: CompanyAgentSpec
) -> str:
    relevant = _relevant_entities(rule, spec)
    return "\n".join(
        [
            f"Company: {spec.company_name}",
            f"Domain context: {spec.domain_context}",
            "",
            f"Rule under evaluation: {rule.name} (id={rule.id}, severity={rule.severity.value}).",
            f"Rule description: {rule.description}",
            "",
            "Relevant entities and their per-system mappings (JSON):",
            json.dumps([em.model_dump() for em in relevant], indent=2),
            "",
            "Reasoning instructions for this rule (placeholder tokens like `{column_name}` refer to fields in the violation row below — substitute the actual values when you write the explanation):",
            rule.reasoning_template,
            "",
            "Corrective action templates available for this rule. Each parameter_mapping value names a column in the violation row; replace it with the actual value when filling the action's parameters (JSON):",
            json.dumps(
                [a.model_dump() for a in rule.corrective_action_templates],
                indent=2,
            ),
            "",
            "Approved company vocabulary — use these terms in the explanation (JSON):",
            json.dumps(spec.vocabulary.model_dump(), indent=2),
            "",
            "Violation row (column -> value, JSON):",
            json.dumps(violation, indent=2, default=str),
            "",
            "Now produce the ReasoningOutput JSON for this violation.",
        ]
    )


def _parse_final_text(text: str) -> ReasoningOutput:
    try:
        return ReasoningOutput.model_validate_json(text)
    except Exception:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            return ReasoningOutput.model_validate_json(fence.group(1))
        brace = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace:
            return ReasoningOutput.model_validate_json(brace.group(1))
        raise


async def reason_about_violation(
    rule: Rule,
    violation: dict[str, Any],
    spec: CompanyAgentSpec,
    *,
    model: str = _DEFAULT_MODEL,
) -> ReasoningOutput:
    agent = LlmAgent(
        name=f"reasoner_{rule.id.lower()}",
        model=model,
        description=f"Per-violation reasoning agent for rule {rule.id}.",
        instruction=_STATIC_INSTRUCTION,
        output_schema=ReasoningOutput,
    )

    session_service = InMemorySessionService()
    session_id = f"viol-{rule.id}-{abs(hash(json.dumps(violation, default=str, sort_keys=True)))}"
    await session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=session_id
    )
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)

    user_msg = types.Content(
        role="user",
        parts=[types.Part(text=_build_user_message(rule, violation, spec))],
    )

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=_USER_ID, session_id=session_id, new_message=user_msg
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text
            # Do not break — let the runner drain cleanly so OpenTelemetry
            # spans detach in the same context they were created in.

    if not final_text:
        raise RuntimeError(f"Agent for rule {rule.id} produced no final response")

    return _parse_final_text(final_text)

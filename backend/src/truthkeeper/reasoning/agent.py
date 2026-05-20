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

from truthkeeper.reasoning.output import DraftedAction, ReasoningOutput
from truthkeeper.spec.models import (
    CompanyAgentSpec,
    CorrectiveActionTemplate,
    EntityModel,
    Rule,
)

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
    "likely root cause, estimates monetary impact when applicable, and drafts one "
    "DraftedAction per corrective action template provided.\n\n"
    "Concentrate your effort on `explanation`, `likely_cause`, and the monetary "
    "impact fields. Each DraftedAction's `description` MUST read as a concrete "
    "human preview with the actual values from the violation row substituted in "
    "(not column names). You may leave `parameters` empty — the system fills "
    "those in deterministically from the rule's parameter_mapping."
)


def resolve_action_parameters(
    template: CorrectiveActionTemplate,
    violation: dict[str, Any],
) -> dict[str, str]:
    """Deterministically resolve a template's parameter_mapping against a row.

    Each value in `parameter_mapping` is either a column name in the violation
    row (look it up) or a literal (pass through). This avoids relying on Gemini
    for dict lookups — Gemini is unreliable there and the substitution is
    fully deterministic from the spec.
    """
    resolved: dict[str, str] = {}
    for param_name, mapping_value in template.parameter_mapping.items():
        if mapping_value in violation:
            value = violation[mapping_value]
            resolved[param_name] = "" if value is None else str(value)
        else:
            resolved[param_name] = mapping_value
    return resolved


def _backfill_parameters(
    output: ReasoningOutput,
    rule: Rule,
    violation: dict[str, Any],
) -> ReasoningOutput:
    templates_by_type = {
        t.action_type: t for t in rule.corrective_action_templates
    }
    fixed: list[DraftedAction] = []
    for action in output.drafted_actions:
        template = templates_by_type.get(action.action_type)
        if template is None:
            fixed.append(action)
            continue
        resolved = resolve_action_parameters(template, violation)
        # Deterministic resolution overrides Gemini's params for known keys,
        # but Gemini-added extras (keys not in the template) are preserved.
        merged = {**action.parameters, **resolved}
        fixed.append(action.model_copy(update={"parameters": merged}))
    return output.model_copy(update={"drafted_actions": fixed})


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
            "Corrective action templates available for this rule. Emit one DraftedAction per template, mirroring its `action_type` and `target_system` and writing a concrete human-readable description (JSON):",
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

    parsed = _parse_final_text(final_text)
    return _backfill_parameters(parsed, rule, violation)

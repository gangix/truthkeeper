"""Structured output Gemini must produce per violation, plus aggregate types.

ReasoningOutput is bound to the agent via ADK's `output_schema` — Gemini sees
it as a JSON schema and emits matching JSON. The aggregate types
(ViolationReasoning / RuleReconciliation / ReconciliationReport) wrap the
agent output with the violation row and rule metadata for downstream UI/API use.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from truthkeeper.spec.models import Severity, SystemName


class DraftedAction(BaseModel):
    """One concrete corrective action against one target system."""

    model_config = ConfigDict(extra="forbid")

    target_system: SystemName = Field(
        description="Which SaaS system this action targets."
    )
    action_type: str = Field(
        description="Short identifier matching the rule's corrective_action_templates."
    )
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Action parameters with VALUES from the violation row filled in "
            "(not column names). Example: {'subscription_id': 'sub_1TYtP8...'}."
        ),
    )
    description: str = Field(
        description=(
            "Human-readable preview of the action with the actual values from "
            "the violation row substituted in."
        ),
    )


class ReasoningOutput(BaseModel):
    """The agent's structured reasoning about one violation."""

    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(
        description=(
            "Plain-language explanation of the disagreement, using the "
            "company's vocabulary."
        ),
    )
    likely_cause: str = Field(
        description="Most plausible root cause of how the disagreement arose."
    )
    monetary_impact_estimate_eur: float | None = Field(
        default=None,
        description=(
            "Best-effort EUR estimate of the financial impact, if applicable. "
            "Omit if the disagreement is not directly monetary."
        ),
    )
    monetary_impact_explanation: str | None = Field(
        default=None,
        description="One-sentence justification of the monetary estimate.",
    )
    drafted_actions: list[DraftedAction] = Field(
        description=(
            "Cross-system corrective actions to propose for one-tap human "
            "approval. Each must be ready to execute once approved."
        ),
    )


class ViolationReasoning(BaseModel):
    """One violation row paired with the agent's reasoning about it."""

    model_config = ConfigDict(extra="forbid")

    violation_id: str = Field(
        description=(
            "Stable hash of (rule.id, row) used as the key for per-action "
            "approvals; see reasoning.orchestrator._violation_id."
        ),
    )
    violation: dict[str, Any] = Field(
        description="The original violation row from BigQuery (JSON-friendly)."
    )
    reasoning: ReasoningOutput


class RuleReconciliation(BaseModel):
    """Aggregate result for one rule's reconciliation pass."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_name: str
    severity: Severity
    violation_count: int = Field(
        description="Total violations the SQL returned, before sampling."
    )
    sampled_count: int = Field(
        description="How many violations were actually sent to Gemini."
    )
    violations: list[ViolationReasoning]


class ReconciliationReport(BaseModel):
    """One full reconciliation pass over every rule in the spec."""

    model_config = ConfigDict(extra="forbid")

    company_id: str
    company_name: str
    rules: list[RuleReconciliation]

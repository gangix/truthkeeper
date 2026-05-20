"""Structured output Gemini must produce per violation.

Bound to the agent via ADK's `output_schema`. Gemini sees this as a JSON
schema and emits matching JSON; we parse it back into Pydantic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from truthkeeper.spec.models import SystemName


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

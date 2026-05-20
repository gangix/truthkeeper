"""Per-violation reasoning loop: BigQuery + ADK + Gemini 3.

The architecture (PROJECT_BRIEF.md §4):
  1. Execute a rule's SQL against BigQuery (deterministic, cheap).
  2. For each violation row, call an ADK LlmAgent powered by Gemini 3 to
     explain the disagreement and draft cross-system corrective actions.
"""

from truthkeeper.reasoning.agent import (
    reason_about_violation,
    resolve_action_parameters,
)
from truthkeeper.reasoning.orchestrator import reconcile_all_rules
from truthkeeper.reasoning.output import (
    DraftedAction,
    ReasoningOutput,
    ReconciliationReport,
    RuleReconciliation,
    ViolationReasoning,
)

__all__ = [
    "DraftedAction",
    "ReasoningOutput",
    "ReconciliationReport",
    "RuleReconciliation",
    "ViolationReasoning",
    "reason_about_violation",
    "reconcile_all_rules",
    "resolve_action_parameters",
]

"""Per-violation reasoning loop: BigQuery + ADK + Gemini 3.

The architecture (PROJECT_BRIEF.md §4):
  1. Execute a rule's SQL against BigQuery (deterministic, cheap).
  2. For each violation row, call an ADK LlmAgent powered by Gemini 3 to
     explain the disagreement and draft cross-system corrective actions.
"""

from truthkeeper.reasoning.output import DraftedAction, ReasoningOutput

__all__ = ["DraftedAction", "ReasoningOutput"]

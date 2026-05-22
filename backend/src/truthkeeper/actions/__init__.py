"""SaaS action executors for the per-violation Approve flow.

One module per partner system. dispatch.py is the entry point used by the
approve endpoint; result.py defines the shared ExecutionResult shape; each
{stripe,salesforce,hubspot}.py module implements the action functions for
that system.
"""

from truthkeeper.actions.dispatch import (
    UnsupportedActionError,
    dispatch_action,
)
from truthkeeper.actions.result import ExecutionResult

__all__ = ["ExecutionResult", "UnsupportedActionError", "dispatch_action"]

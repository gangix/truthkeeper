"""HTTP API surface for TruthKeeper.

Endpoints are grouped per resource (companies, disagreements, etc.). The
backend keeps a single hardcoded demo company for now — the onboarding
flow that creates new CompanyAgentSpec instances lands in Phase 2.
"""

from truthkeeper.api.companies import router as companies_router

__all__ = ["companies_router"]

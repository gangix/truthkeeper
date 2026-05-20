"""Company-scoped endpoints: spec lookup and reconciliation pass.

Only one company is wired up in Phase 1 (`truthkeeper-demo`); the
onboarding flow that produces new CompanyAgentSpec instances lands in
Phase 2.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from truthkeeper.reasoning.orchestrator import reconcile_all_rules
from truthkeeper.reasoning.output import ReconciliationReport
from truthkeeper.spec.demo import DEMO_SPEC
from truthkeeper.spec.models import CompanyAgentSpec

router = APIRouter(prefix="/companies", tags=["companies"])

_SPECS_BY_ID: dict[str, CompanyAgentSpec] = {DEMO_SPEC.company_id: DEMO_SPEC}


class ReconcileRequest(BaseModel):
    rule_ids: list[str] | None = Field(
        default=None,
        description=(
            "Optional filter: only reconcile these rule ids (e.g. ['D1', 'D2']). "
            "Defaults to running every rule in the company's spec."
        ),
    )


def _require_spec(company_id: str) -> CompanyAgentSpec:
    spec = _SPECS_BY_ID.get(company_id)
    if spec is None:
        raise HTTPException(
            status_code=404,
            detail=f"No CompanyAgentSpec registered for company_id={company_id!r}",
        )
    return spec


@router.get("/{company_id}/spec", response_model=CompanyAgentSpec)
def get_spec(
    company_id: Annotated[str, Path(description="Company identifier")],
) -> CompanyAgentSpec:
    return _require_spec(company_id)


@router.post(
    "/{company_id}/reconcile",
    response_model=ReconciliationReport,
)
async def reconcile(
    company_id: Annotated[str, Path(description="Company identifier")],
    max_violations_per_rule: Annotated[
        int,
        Query(
            ge=1,
            le=20,
            description="Cap on violations per rule that get reasoned about.",
        ),
    ] = 3,
    body: ReconcileRequest | None = None,
) -> ReconciliationReport:
    spec = _require_spec(company_id)
    rule_ids = body.rule_ids if body and body.rule_ids else None
    return await reconcile_all_rules(
        spec=spec,
        max_violations_per_rule=max_violations_per_rule,
        rule_ids=rule_ids,
    )

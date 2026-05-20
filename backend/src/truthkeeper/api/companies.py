"""Company-scoped endpoints: spec lookup and reconciliation pass.

Specs are now persisted in Neon Postgres. On boot, `db.bootstrap.init_db()`
seeds DEMO_SPEC if the specs table is empty so the live demo URL keeps
working.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from truthkeeper.db.models import Spec
from truthkeeper.db.session import get_session
from truthkeeper.reasoning.orchestrator import reconcile_all_rules
from truthkeeper.reasoning.output import ReconciliationReport
from truthkeeper.spec.models import CompanyAgentSpec

router = APIRouter(prefix="/companies", tags=["companies"])


class ReconcileRequest(BaseModel):
    rule_ids: list[str] | None = Field(
        default=None,
        description=(
            "Optional filter: only reconcile these rule ids (e.g. ['D1', 'D2']). "
            "Defaults to running every rule in the company's spec."
        ),
    )


async def _require_spec(company_id: str, session: AsyncSession) -> CompanyAgentSpec:
    row = (
        await session.execute(select(Spec).where(Spec.company_id == company_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No CompanyAgentSpec persisted for company_id={company_id!r}",
        )
    try:
        return CompanyAgentSpec.model_validate(row.spec_json)
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Spec for company_id={company_id!r} failed validation: "
                f"{exc.error_count()} error(s)"
            ),
        ) from exc


@router.get("/{company_id}/spec", response_model=CompanyAgentSpec)
async def get_spec(
    company_id: Annotated[str, Path(description="Company identifier")],
    session: AsyncSession = Depends(get_session),
) -> CompanyAgentSpec:
    return await _require_spec(company_id, session)


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
    session: AsyncSession = Depends(get_session),
) -> ReconciliationReport:
    spec = await _require_spec(company_id, session)
    rule_ids = body.rule_ids if body and body.rule_ids else None
    return await reconcile_all_rules(
        spec=spec,
        max_violations_per_rule=max_violations_per_rule,
        rule_ids=rule_ids,
    )

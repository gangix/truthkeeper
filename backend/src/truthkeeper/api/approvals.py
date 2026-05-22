"""HTTP surface for per-action approve + approval history lookup."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from truthkeeper.actions import (
    ExecutionResult,
    UnsupportedActionError,
    dispatch_action,
)
from truthkeeper.db.models import Approval
from truthkeeper.db.session import get_session
from truthkeeper.reasoning.agent import resolve_action_parameters
from truthkeeper.reasoning.orchestrator import get_cached_violation
from truthkeeper.spec.models import SystemName

router = APIRouter(prefix="/companies", tags=["approvals"])
logger = logging.getLogger(__name__)


class ApprovalResponse(BaseModel):
    execution_result: ExecutionResult
    approval_id: str


class ApprovalSummary(BaseModel):
    approval_id: str
    action_idx: int
    target_system: SystemName
    action_type: str
    status: Literal["succeeded", "failed"]
    external_id: str | None
    message: str
    error: str | None
    executed_at: str


async def _persist(
    session: AsyncSession,
    *,
    company_id: str,
    rule_id: str,
    violation_id: str,
    action_idx: int,
    target_system: SystemName,
    action_type: str,
    parameters: dict[str, str],
    result: ExecutionResult,
) -> str:
    approval_id = uuid.uuid4().hex
    session.add(
        Approval(
            id=approval_id,
            company_id=company_id,
            rule_id=rule_id,
            violation_id=violation_id,
            action_idx=action_idx,
            target_system=target_system.value,
            action_type=action_type,
            parameters_json=parameters,
            status=result.status,
            external_id=result.external_id,
            message=result.message,
            error=result.error,
        )
    )
    await session.commit()
    return approval_id


@router.post(
    "/{company_id}/disagreements/{violation_id}/actions/{action_idx}/approve",
    response_model=ApprovalResponse,
)
async def approve_action(
    company_id: Annotated[str, Path(description="Company identifier")],
    violation_id: Annotated[str, Path(description="Stable violation hash id")],
    action_idx: Annotated[int, Path(ge=0, description="Index into corrective_action_templates")],
    session: AsyncSession = Depends(get_session),
) -> ApprovalResponse:
    cached = get_cached_violation(violation_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="Reconciliation expired; re-run reconciliation to refresh disagreements.",
        )
    rule, row, _reasoning = cached

    if action_idx >= len(rule.corrective_action_templates):
        raise HTTPException(
            status_code=400,
            detail=(
                f"action_idx {action_idx} out of range; "
                f"rule has {len(rule.corrective_action_templates)} actions"
            ),
        )

    template = rule.corrective_action_templates[action_idx]
    parameters = resolve_action_parameters(template, row)

    try:
        result = await dispatch_action(
            template.target_system, template.action_type, parameters
        )
    except UnsupportedActionError as exc:
        result = ExecutionResult(
            status="failed",
            error=f"UnsupportedActionError: {exc}",
        )
        approval_id = await _persist(
            session,
            company_id=company_id,
            rule_id=rule.id,
            violation_id=violation_id,
            action_idx=action_idx,
            target_system=template.target_system,
            action_type=template.action_type,
            parameters=parameters,
            result=result,
        )
        raise HTTPException(
            status_code=501,
            detail={"execution_result": result.model_dump(), "approval_id": approval_id},
        )

    approval_id = await _persist(
        session,
        company_id=company_id,
        rule_id=rule.id,
        violation_id=violation_id,
        action_idx=action_idx,
        target_system=template.target_system,
        action_type=template.action_type,
        parameters=parameters,
        result=result,
    )
    return ApprovalResponse(execution_result=result, approval_id=approval_id)


@router.get(
    "/{company_id}/approvals/by-violation/{violation_id}",
    response_model=list[ApprovalSummary],
)
async def list_approvals_by_violation(
    company_id: Annotated[str, Path(description="Company identifier")],
    violation_id: Annotated[str, Path(description="Stable violation hash id")],
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalSummary]:
    rows = (
        await session.execute(
            select(Approval)
            .where(Approval.company_id == company_id)
            .where(Approval.violation_id == violation_id)
            .order_by(Approval.executed_at.asc())
        )
    ).scalars().all()
    return [
        ApprovalSummary(
            approval_id=r.id,
            action_idx=r.action_idx,
            target_system=SystemName(r.target_system),
            action_type=r.action_type,
            status=r.status,  # type: ignore[arg-type]
            external_id=r.external_id,
            message=r.message,
            error=r.error,
            executed_at=r.executed_at.isoformat(),
        )
        for r in rows
    ]

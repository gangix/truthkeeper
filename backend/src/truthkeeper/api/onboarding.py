"""Onboarding HTTP surface: SSE stream of stage events + approve endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from truthkeeper.db.models import Company, Spec
from truthkeeper.db.session import get_session
from truthkeeper.onboarding.pipeline import get_cached_proposal, run_onboarding
from truthkeeper.onboarding.proposal import OnboardingProposal
from truthkeeper.spec.models import (
    CompanyAgentSpec,
    ConnectedSystem,
    CorrectiveActionTemplate,
    DomainTerm,
    EntityMapping,
    EntityModel,
    Rule,
    SystemName,
    Vocabulary,
)

router = APIRouter(prefix="/companies", tags=["onboarding"])
logger = logging.getLogger(__name__)


@router.get("/{company_id}/onboard/stream")
async def stream_onboarding(
    company_id: Annotated[str, Path(description="Company identifier")],
) -> StreamingResponse:
    """Server-Sent Events: emits one event per pipeline stage."""

    async def event_source():
        try:
            async for event in run_onboarding(company_id):
                yield f"data: {event.model_dump_json()}\n\n"
        except asyncio.CancelledError:
            logger.info("onboard/stream cancelled by client for %s", company_id)
            raise

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class ApprovalRequest(BaseModel):
    proposal_id: str
    company_name: str = Field(default="TruthKeeper Demo Co")
    accepted_entity_ids: list[str] = Field(default_factory=list)
    accepted_rule_ids: list[str] = Field(default_factory=list)
    accepted_vocab_ids: list[str] = Field(default_factory=list)


def _assemble_spec(
    *,
    company_id: str,
    company_name: str,
    proposal: OnboardingProposal,
    selection: ApprovalRequest,
    connected_systems: list[ConnectedSystem],
) -> CompanyAgentSpec:
    entity_ids = set(selection.accepted_entity_ids)
    rule_ids = set(selection.accepted_rule_ids)
    vocab_ids = set(selection.accepted_vocab_ids)

    entity_model = [
        EntityModel(
            name=e.name,
            mappings=[
                EntityMapping(
                    system=SystemName(m.system),
                    table=m.table,
                    id_field=m.id_field,
                    email_field=m.email_field,
                    status_field=m.status_field,
                )
                for m in e.mappings
            ],
        )
        for e in proposal.entities
        if e.proposal_id in entity_ids
    ]

    # Rule sql / reasoning_template / corrective_action_templates / monetary_impact_formula
    # are pinned to DEMO_SPEC by rule id (the SynthesisAgent only chooses which
    # rule ids to include + emits stubs for the pinned fields, since those
    # contain `{column_name}` placeholders that ADK's instruction templater
    # cannot pass through unchanged). We look them up here at approve-time.
    from truthkeeper.spec.demo import DEMO_SPEC as _DEMO

    _demo_rules_by_id = {dr.id: dr for dr in _DEMO.rules}
    rules: list[Rule] = []
    for r in proposal.rules:
        if r.proposal_id not in rule_ids:
            continue
        demo_rule = _demo_rules_by_id.get(r.id)
        if demo_rule is None:
            # Agent hallucinated an id; skip it rather than 500.
            continue
        rules.append(
            Rule(
                id=demo_rule.id,
                name=demo_rule.name,
                description=demo_rule.description,
                severity=demo_rule.severity,
                sql=demo_rule.sql,
                reasoning_template=demo_rule.reasoning_template,
                corrective_action_templates=demo_rule.corrective_action_templates,
                monetary_impact_formula=demo_rule.monetary_impact_formula,
            )
        )

    vocab_terms = [
        DomainTerm(canonical=v.canonical, aliases=v.aliases)
        for v in proposal.vocabulary
        if v.proposal_id in vocab_ids
    ]

    return CompanyAgentSpec(
        company_id=company_id,
        company_name=company_name,
        connected_systems=connected_systems,
        entity_model=entity_model,
        rules=rules,
        vocabulary=Vocabulary(domain_terms=vocab_terms),
        tool_parameters={},
        domain_context="",
    )


@router.post("/{company_id}/onboard/approve", response_model=CompanyAgentSpec)
async def approve_onboarding(
    company_id: Annotated[str, Path(description="Company identifier")],
    body: ApprovalRequest,
    session: AsyncSession = Depends(get_session),
) -> CompanyAgentSpec:
    proposal = get_cached_proposal(body.proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=404,
            detail="Proposal expired or never seen; re-run onboarding.",
        )
    if not body.accepted_entity_ids or not body.accepted_rule_ids:
        raise HTTPException(
            status_code=400,
            detail="Must accept at least one entity and one rule.",
        )

    # Connected systems are not in the proposal (Fivetran metadata is in
    # session state, not OnboardingProposal). For the demo, reuse the live
    # Fivetran connector ids from the existing DEMO_SPEC.
    from truthkeeper.spec.demo import DEMO_SPEC

    connected_systems = DEMO_SPEC.connected_systems

    spec = _assemble_spec(
        company_id=company_id,
        company_name=body.company_name,
        proposal=proposal,
        selection=body,
        connected_systems=connected_systems,
    )

    existing_company = (
        await session.execute(select(Company).where(Company.id == company_id))
    ).scalar_one_or_none()
    if existing_company is None:
        session.add(Company(id=company_id, name=body.company_name))

    existing_spec = (
        await session.execute(select(Spec).where(Spec.company_id == company_id))
    ).scalar_one_or_none()
    if existing_spec is None:
        session.add(
            Spec(
                company_id=company_id,
                spec_json=json.loads(spec.model_dump_json()),
                version=1,
                agent_run_id=proposal.source_run_id,
            )
        )
    else:
        existing_spec.spec_json = json.loads(spec.model_dump_json())
        existing_spec.version = existing_spec.version + 1
        existing_spec.agent_run_id = proposal.source_run_id

    await session.commit()
    return spec

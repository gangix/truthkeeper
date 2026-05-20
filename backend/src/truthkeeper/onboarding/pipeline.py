"""Drives onboarding_pipeline and yields one StageEvent per stage finalization.

Also keeps a process-memory dict of {proposal_id -> OnboardingProposal} so the
approve endpoint can resolve the user's row-level selections back to items.
Process restart drops the cache; the UI surfaces a "Proposal expired" message
in that case (see Task 10 error path).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from truthkeeper.onboarding.agents import build_onboarding_pipeline
from truthkeeper.onboarding.proposal import OnboardingProposal

logger = logging.getLogger(__name__)

_APP_NAME = "truthkeeper-onboarding"
_USER_ID = "onboarding-user"

Stage = Literal["discovery", "profiling", "synthesis"]


class StageEvent(BaseModel):
    stage: Stage
    payload: dict[str, Any] | None = None
    error: str | None = None
    done: bool


_PROPOSAL_CACHE: dict[str, OnboardingProposal] = {}


def get_cached_proposal(proposal_id: str) -> OnboardingProposal | None:
    return _PROPOSAL_CACHE.get(proposal_id)


_AUTHOR_TO_STAGE: dict[str, Stage] = {
    "DiscoveryAgent": "discovery",
    "ProfilingAgent": "profiling",
    "SynthesisAgent": "synthesis",
}


def _parse_synthesis_text(text: str) -> OnboardingProposal:
    """Mirror reasoning/agent.py:147 leniency for fenced / wrapped JSON."""
    try:
        return OnboardingProposal.model_validate_json(text)
    except Exception:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            return OnboardingProposal.model_validate_json(fenced.group(1))
        brace = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace:
            return OnboardingProposal.model_validate_json(brace.group(1))
        raise


PIPELINE_TIMEOUT_SECONDS = 270  # Three 90s stages per spec §7.3 + 30s headroom


async def run_onboarding(company_id: str) -> AsyncIterator[StageEvent]:
    """Yield one StageEvent per sub-agent finalization plus the terminal synthesis event.

    Bounds total wall time at PIPELINE_TIMEOUT_SECONDS to stay safely under
    Cloud Run's 300s request cap.
    """
    pipeline = build_onboarding_pipeline()
    session_service = InMemorySessionService()
    session_id = f"onboard-{company_id}-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=session_id
    )
    runner = Runner(agent=pipeline, app_name=_APP_NAME, session_service=session_service)

    prompt = (
        f"Onboard company {company_id}: discover Fivetran connectors and schemas, "
        "profile the discovered tables, and synthesize an OnboardingProposal."
    )
    user_msg = types.Content(role="user", parts=[types.Part(text=prompt)])

    final_synthesis_text: str | None = None
    last_seen_stage: Stage = "discovery"
    try:
        async with asyncio.timeout(PIPELINE_TIMEOUT_SECONDS):
            async for event in runner.run_async(
                user_id=_USER_ID, session_id=session_id, new_message=user_msg
            ):
                if not event.is_final_response():
                    continue
                author = event.author or ""
                stage = _AUTHOR_TO_STAGE.get(author)
                if stage is None:
                    continue
                last_seen_stage = stage
                text = (event.content.parts[0].text or "") if event.content and event.content.parts else ""
                logger.info("stage=%s author=%s text_len=%d", stage, author, len(text))

                if stage in ("discovery", "profiling"):
                    yield StageEvent(
                        stage=stage,
                        payload={"summary": text},
                        done=False,
                    )
                else:  # synthesis
                    final_synthesis_text = text
    except TimeoutError:
        logger.error("onboarding pipeline exceeded %ds at stage=%s",
                     PIPELINE_TIMEOUT_SECONDS, last_seen_stage)
        yield StageEvent(
            stage=last_seen_stage,
            error=f"Pipeline exceeded {PIPELINE_TIMEOUT_SECONDS}s timeout",
            done=True,
        )
        return
    except Exception as exc:
        logger.exception("onboarding pipeline raised")
        yield StageEvent(stage=last_seen_stage, error=str(exc), done=True)
        return

    if not final_synthesis_text:
        yield StageEvent(stage="synthesis", error="SynthesisAgent produced no final response", done=True)
        return

    try:
        proposal = _parse_synthesis_text(final_synthesis_text)
    except Exception as exc:
        yield StageEvent(stage="synthesis", error=f"Synthesis JSON invalid: {exc}", done=True)
        return

    _PROPOSAL_CACHE[proposal.proposal_id] = proposal
    yield StageEvent(stage="synthesis", payload=json.loads(proposal.model_dump_json()), done=True)

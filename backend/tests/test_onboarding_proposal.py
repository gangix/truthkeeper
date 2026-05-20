"""Pydantic shape smoke test for the OnboardingProposal."""

from truthkeeper.onboarding.proposal import (
    OnboardingProposal,
    ProposedEntity,
    ProposedEntityMapping,
    ProposedRule,
    ProposedVocabularyTerm,
)
from truthkeeper.spec.models import Severity, SystemName


def test_proposal_round_trips_via_json() -> None:
    p = OnboardingProposal(
        proposal_id="abc-123",
        entities=[
            ProposedEntity(
                proposal_id="ent-1",
                name="Customer",
                mappings=[
                    ProposedEntityMapping(
                        system=SystemName.salesforce,
                        table="account",
                        id_field="id",
                        email_field="email",
                    )
                ],
            )
        ],
        rules=[
            ProposedRule(
                proposal_id="rule-1",
                id="D1",
                name="Active sub for churned account",
                description="...",
                severity=Severity.critical,
                sql="SELECT 1",
                reasoning_template="...",
                corrective_action_templates=[],
                monetary_impact_formula=None,
            )
        ],
        vocabulary=[
            ProposedVocabularyTerm(proposal_id="v-1", canonical="Customer", aliases=["Account"])
        ],
        source_run_id="run-1",
    )
    j = p.model_dump_json()
    OnboardingProposal.model_validate_json(j)

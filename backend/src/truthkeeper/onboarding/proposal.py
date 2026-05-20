"""Pydantic models for the SequentialAgent's intermediate + final outputs.

DiscoveredSchema / ColumnProfile are intermediate stage payloads streamed to
the UI. OnboardingProposal is the SynthesisAgent's structured output schema
and the source of truth for what the approve endpoint persists.

Every proposed item carries a stable `proposal_id` (UUID-like string) so the
UI can toggle and the approve endpoint can resolve the user's selection back
to items by id.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from truthkeeper.spec.models import Severity, SystemName


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TableSchema(_Frozen):
    name: str
    columns: list[dict[str, Any]] = Field(default_factory=list)


class DiscoveredSchema(_Frozen):
    connector_id: str
    system: SystemName
    bigquery_dataset: str
    tables: list[TableSchema]


class DiscoveredSchemas(_Frozen):
    schemas: list[DiscoveredSchema]


class ColumnProfileEntry(_Frozen):
    column: str
    cardinality: int | Literal["high"]
    distinct_values: list[dict[str, Any]] | None = None
    error: str | None = None


class TableProfile(_Frozen):
    dataset: str
    table: str
    columns: list[ColumnProfileEntry]


class ColumnProfiles(_Frozen):
    profiles: list[TableProfile]


class ProposedEntityMapping(_Frozen):
    system: SystemName
    table: str
    id_field: str
    email_field: str | None = None
    status_field: str | None = None


class ProposedEntity(_Frozen):
    proposal_id: str
    name: str
    mappings: list[ProposedEntityMapping]


class ProposedCorrectiveActionTemplate(_Frozen):
    target_system: SystemName
    action_type: str
    parameter_mapping: dict[str, str] = Field(default_factory=dict)
    description: str


class ProposedRule(_Frozen):
    proposal_id: str
    id: str
    name: str
    description: str
    severity: Severity
    sql: str
    reasoning_template: str
    corrective_action_templates: list[ProposedCorrectiveActionTemplate] = Field(
        default_factory=list
    )
    monetary_impact_formula: str | None = None


class ProposedVocabularyTerm(_Frozen):
    proposal_id: str
    canonical: str
    aliases: list[str] = Field(default_factory=list)


class OnboardingProposal(_Frozen):
    proposal_id: str
    entities: list[ProposedEntity]
    rules: list[ProposedRule]
    vocabulary: list[ProposedVocabularyTerm]
    source_run_id: str

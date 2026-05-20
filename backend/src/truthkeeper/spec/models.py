"""Pydantic models for CompanyAgentSpec — see PROJECT_BRIEF.md §4.

The agent's behavior is a pure function of one CompanyAgentSpec plus live
data from BigQuery. Two companies running the same agent code end up with
different behavior because their specs differ — that's the "shaped per
company" property.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SystemName(StrEnum):
    salesforce = "salesforce"
    stripe = "stripe"
    hubspot = "hubspot"


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntityMapping(_Spec):
    system: SystemName
    table: str
    id_field: str
    email_field: str | None = None
    status_field: str | None = None
    extra_fields: dict[str, str] = Field(default_factory=dict)


class EntityModel(_Spec):
    name: str
    mappings: list[EntityMapping]


class CorrectiveActionTemplate(_Spec):
    target_system: SystemName
    action_type: str
    parameter_mapping: dict[str, str] = Field(default_factory=dict)
    description: str


class Rule(_Spec):
    id: str
    name: str
    description: str
    severity: Severity
    sql: str
    reasoning_template: str
    corrective_action_templates: list[CorrectiveActionTemplate]
    monetary_impact_formula: str | None = None


class ConnectedSystem(_Spec):
    name: SystemName
    fivetran_connector_id: str
    bigquery_dataset: str
    schema_snapshot: dict[str, Any] = Field(default_factory=dict)
    sample_data: dict[str, Any] = Field(default_factory=dict)


class DomainTerm(_Spec):
    canonical: str
    aliases: list[str] = Field(default_factory=list)


class CustomField(_Spec):
    system: SystemName
    field: str
    semantic_type: str


class Vocabulary(_Spec):
    domain_terms: list[DomainTerm] = Field(default_factory=list)
    custom_fields: list[CustomField] = Field(default_factory=list)
    status_labels: list[DomainTerm] = Field(default_factory=list)


class CompanyAgentSpec(_Spec):
    company_id: str
    company_name: str
    connected_systems: list[ConnectedSystem]
    entity_model: list[EntityModel]
    rules: list[Rule]
    vocabulary: Vocabulary = Field(default_factory=Vocabulary)
    tool_parameters: dict[SystemName, dict[str, str]] = Field(default_factory=dict)
    domain_context: str = ""

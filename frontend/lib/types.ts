// Mirrors backend/src/truthkeeper/reasoning/output.py and spec/models.py.
// Hand-maintained for hackathon speed; auto-generate from the OpenAPI schema
// once the API surface stabilises.

export type SystemName = "salesforce" | "stripe" | "hubspot";

export type Severity = "critical" | "high" | "medium" | "low";

export interface DraftedAction {
  target_system: SystemName;
  action_type: string;
  parameters: Record<string, string>;
  description: string;
}

export interface ReasoningOutput {
  explanation: string;
  likely_cause: string;
  monetary_impact_estimate_eur: number | null;
  monetary_impact_explanation: string | null;
  drafted_actions: DraftedAction[];
}

export interface ViolationReasoning {
  violation: Record<string, unknown>;
  reasoning: ReasoningOutput;
}

export interface RuleReconciliation {
  rule_id: string;
  rule_name: string;
  severity: Severity;
  violation_count: number;
  sampled_count: number;
  violations: ViolationReasoning[];
}

export interface ReconciliationReport {
  company_id: string;
  company_name: string;
  rules: RuleReconciliation[];
}

export interface ConnectedSystem {
  name: SystemName;
  fivetran_connector_id: string;
  bigquery_dataset: string;
}

export interface CompanyAgentSpec {
  company_id: string;
  company_name: string;
  connected_systems: ConnectedSystem[];
  rules: { id: string; name: string; severity: Severity; description: string }[];
}

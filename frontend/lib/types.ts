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
  violation_id: string;
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

// ---- Onboarding (mirrors backend/src/truthkeeper/onboarding/proposal.py + pipeline.py) ----

export interface ProposedEntityMapping {
  system: SystemName;
  table: string;
  id_field: string;
  email_field?: string | null;
  status_field?: string | null;
}

export interface ProposedEntity {
  proposal_id: string;
  name: string;
  mappings: ProposedEntityMapping[];
}

export interface ProposedCorrectiveActionTemplate {
  target_system: SystemName;
  action_type: string;
  parameter_mapping: Record<string, string>;
  description: string;
}

export interface ProposedRule {
  proposal_id: string;
  id: string;
  name: string;
  description: string;
  severity: Severity;
  sql: string;
  reasoning_template: string;
  corrective_action_templates: ProposedCorrectiveActionTemplate[];
  monetary_impact_formula: string | null;
}

export interface ProposedVocabularyTerm {
  proposal_id: string;
  canonical: string;
  aliases: string[];
}

export interface OnboardingProposal {
  proposal_id: string;
  entities: ProposedEntity[];
  rules: ProposedRule[];
  vocabulary: ProposedVocabularyTerm[];
  source_run_id: string;
}

export type StageEventStage = "discovery" | "profiling" | "synthesis";

export interface StageEvent {
  stage: StageEventStage;
  payload?: { summary?: string } | OnboardingProposal | null;
  error?: string | null;
  done: boolean;
}

export interface ApprovalRequest {
  proposal_id: string;
  company_name: string;
  accepted_entity_ids: string[];
  accepted_rule_ids: string[];
  accepted_vocab_ids: string[];
}

// ---- Approvals (mirrors backend/src/truthkeeper/api/approvals.py) ----

export interface ExecutionResult {
  status: "succeeded" | "failed";
  external_id: string | null;
  message: string;
  error: string | null;
}

export interface ApprovalResponse {
  execution_result: ExecutionResult;
  approval_id: string;
}

export interface ApprovalSummary {
  approval_id: string;
  action_idx: number;
  target_system: SystemName;
  action_type: string;
  status: "succeeded" | "failed";
  external_id: string | null;
  message: string;
  error: string | null;
  executed_at: string;
}

import type {
  ApprovalRequest,
  ApprovalResponse,
  ApprovalSummary,
  CompanyAgentSpec,
  OnboardingProposal,
  ReconciliationReport,
  StageEvent,
} from "@/lib/types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";

export const DEMO_COMPANY_ID = "truthkeeper-demo";

export async function fetchSpec(
  companyId: string = DEMO_COMPANY_ID,
): Promise<CompanyAgentSpec> {
  const res = await fetch(`${BACKEND_URL}/companies/${companyId}/spec`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`spec fetch failed: ${res.status}`);
  return res.json();
}

export async function runReconcile(
  companyId: string = DEMO_COMPANY_ID,
  options?: { maxViolationsPerRule?: number; ruleIds?: string[] },
): Promise<ReconciliationReport> {
  const max = options?.maxViolationsPerRule ?? 1;
  const url = `${BACKEND_URL}/companies/${companyId}/reconcile?max_violations_per_rule=${max}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rule_ids: options?.ruleIds ?? null }),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`reconcile failed (${res.status}): ${detail}`);
  }
  return res.json();
}

export function streamOnboarding(
  companyId: string = DEMO_COMPANY_ID,
  onEvent: (event: StageEvent) => void,
  onError: (err: Error) => void,
): () => void {
  const url = `${BACKEND_URL}/companies/${companyId}/onboard/stream`;
  const es = new EventSource(url);
  es.onmessage = (msg) => {
    try {
      const parsed = JSON.parse(msg.data) as StageEvent;
      onEvent(parsed);
      if (parsed.done) es.close();
    } catch (e) {
      onError(e as Error);
      es.close();
    }
  };
  es.onerror = () => {
    onError(new Error("SSE connection error"));
    es.close();
  };
  return () => es.close();
}

export async function approveOnboarding(
  companyId: string,
  body: ApprovalRequest,
): Promise<CompanyAgentSpec> {
  const res = await fetch(
    `${BACKEND_URL}/companies/${companyId}/onboard/approve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    },
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`approve failed (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function approveAction(
  companyId: string,
  violationId: string,
  actionIdx: number,
): Promise<ApprovalResponse> {
  const res = await fetch(
    `${BACKEND_URL}/companies/${companyId}/disagreements/${violationId}/actions/${actionIdx}/approve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`approve failed (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function getApprovalsByViolation(
  companyId: string,
  violationId: string,
): Promise<ApprovalSummary[]> {
  const res = await fetch(
    `${BACKEND_URL}/companies/${companyId}/approvals/by-violation/${violationId}`,
    { cache: "no-store" },
  );
  if (!res.ok) {
    throw new Error(`approval history fetch failed (${res.status})`);
  }
  return res.json();
}

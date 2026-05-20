import type {
  CompanyAgentSpec,
  ReconciliationReport,
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

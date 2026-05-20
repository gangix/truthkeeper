"use client";

import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Loader2, Play, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ViolationDetailDialog } from "@/app/components/ViolationDetailDialog";
import { fetchSpec, runReconcile } from "@/lib/api";
import { SeverityBadge, SystemBadge } from "@/lib/badges";
import type {
  CompanyAgentSpec,
  ReconciliationReport,
  RuleReconciliation,
  ViolationReasoning,
} from "@/lib/types";

export default function Home() {
  const [spec, setSpec] = useState<CompanyAgentSpec | null>(null);
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{
    rule: RuleReconciliation;
    violation: ViolationReasoning;
  } | null>(null);

  useEffect(() => {
    fetchSpec()
      .then(setSpec)
      .catch((e: Error) => setError(`spec load: ${e.message}`));
  }, []);

  const reconcileNow = async () => {
    setRunning(true);
    setError(null);
    setReport(null);
    try {
      const r = await runReconcile();
      setReport(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const totalViolations =
    report?.rules.reduce((sum, r) => sum + r.violation_count, 0) ?? 0;

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <div className="flex items-center justify-between gap-6 flex-wrap">
            <div className="space-y-2">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                TruthKeeper
              </p>
              <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
                {spec?.company_name ?? <Skeleton className="h-9 w-72" />}
              </h1>
              <p className="text-sm text-muted-foreground italic">
                Your stack is lying to itself.
              </p>
            </div>
            <Button
              size="lg"
              onClick={reconcileNow}
              disabled={running || !spec}
              className="min-w-[180px]"
            >
              {running ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Reconciling…
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Run reconciliation
                </>
              )}
            </Button>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span className="uppercase tracking-wider text-xs">Connected:</span>
            {spec ? (
              spec.connected_systems.map((s) => (
                <SystemBadge key={s.name} system={s.name} />
              ))
            ) : (
              <Skeleton className="h-6 w-48" />
            )}
            {spec && (
              <>
                <span className="text-muted-foreground/40">·</span>
                <span className="text-xs">
                  {spec.rules.length} reconciliation rule
                  {spec.rules.length === 1 ? "" : "s"}
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-10">
        {error && (
          <div className="mb-6 rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-700 dark:text-rose-300">
            <AlertTriangle className="mr-2 inline h-4 w-4" />
            {error}
          </div>
        )}

        {!report && !running && (
          <div className="rounded-xl border bg-card p-10 text-center">
            <Activity className="mx-auto h-10 w-10 text-muted-foreground" />
            <h2 className="mt-4 text-lg font-semibold">No reconciliation yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
              Click <em>Run reconciliation</em> to query BigQuery and reason about
              every cross-system disagreement with Gemini 3.
            </p>
          </div>
        )}

        {running && <RunningState ruleCount={spec?.rules.length ?? 5} />}

        {report && !running && (
          <>
            <div className="mb-6 flex items-baseline justify-between">
              <div>
                <h2 className="text-xl font-bold">Disagreements</h2>
                <p className="text-sm text-muted-foreground">
                  {totalViolations} violation{totalViolations === 1 ? "" : "s"} across{" "}
                  {report.rules.length} rule
                  {report.rules.length === 1 ? "" : "s"}
                </p>
              </div>
            </div>
            <div className="grid gap-4">
              {report.rules.map((rule) => (
                <RuleCard
                  key={rule.rule_id}
                  rule={rule}
                  onSelectViolation={(v) =>
                    setSelected({ rule, violation: v })
                  }
                />
              ))}
            </div>
          </>
        )}
      </section>

      <ViolationDetailDialog
        open={selected !== null}
        onOpenChange={(o) => !o && setSelected(null)}
        rule={selected?.rule ?? null}
        violation={selected?.violation ?? null}
      />
    </main>
  );
}

function RunningState({ ruleCount }: { ruleCount: number }) {
  return (
    <div className="rounded-xl border bg-card p-10 text-center">
      <Loader2 className="mx-auto h-10 w-10 animate-spin text-muted-foreground" />
      <h2 className="mt-4 text-lg font-semibold">Reasoning…</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
        Executing {ruleCount} BigQuery SQL pass{ruleCount === 1 ? "" : "es"} and
        fanning out per-violation reasoning to Gemini 3 in parallel. This usually
        takes 20–40 seconds.
      </p>
    </div>
  );
}

function RuleCard({
  rule,
  onSelectViolation,
}: {
  rule: RuleReconciliation;
  onSelectViolation: (v: ViolationReasoning) => void;
}) {
  const violations = rule.violations;
  const hasViolations = violations.length > 0;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <span className="rounded-md bg-muted px-2 py-1 text-xs font-mono">
              {rule.rule_id}
            </span>
            <SeverityBadge severity={rule.severity} />
            <CardTitle className="text-base">{rule.rule_name}</CardTitle>
          </div>
          <div className="flex items-center gap-2 text-sm">
            {rule.violation_count === 0 ? (
              <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-300">
                <ShieldCheck className="h-4 w-4" />
                No violations
              </span>
            ) : (
              <span className="font-mono">
                {rule.violation_count} violation
                {rule.violation_count === 1 ? "" : "s"}
                {rule.sampled_count < rule.violation_count && (
                  <span className="text-muted-foreground">
                    {" "}
                    · {rule.sampled_count} reasoned
                  </span>
                )}
              </span>
            )}
          </div>
        </div>
      </CardHeader>
      {hasViolations && (
        <CardContent className="space-y-2 pt-0">
          {violations.map((v, i) => (
            <ViolationRow
              key={i}
              violation={v}
              onClick={() => onSelectViolation(v)}
            />
          ))}
        </CardContent>
      )}
    </Card>
  );
}

function ViolationRow({
  violation,
  onClick,
}: {
  violation: ViolationReasoning;
  onClick: () => void;
}) {
  const monetary = violation.reasoning.monetary_impact_estimate_eur;
  return (
    <button
      onClick={onClick}
      className="block w-full rounded-lg border bg-background/60 p-4 text-left transition hover:border-foreground/20 hover:bg-background"
    >
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm leading-relaxed line-clamp-3">
          {violation.reasoning.explanation}
        </p>
        {monetary !== null && (
          <span className="shrink-0 rounded-md bg-amber-500/15 px-2 py-1 text-sm font-bold tabular-nums text-amber-700 dark:text-amber-300">
            €
            {monetary.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}
          </span>
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">Proposes:</span>
        {violation.reasoning.drafted_actions.map((a, i) => (
          <SystemBadge key={i} system={a.target_system} />
        ))}
      </div>
    </button>
  );
}

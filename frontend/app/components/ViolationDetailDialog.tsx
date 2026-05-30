"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, ChevronRight, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { SeverityBadge, SystemBadge } from "@/lib/badges";
import {
  approveAction,
  DEMO_COMPANY_ID,
  getApprovalsByViolation,
} from "@/lib/api";
import type {
  ApprovalSummary,
  DraftedAction,
  ExecutionResult,
  RuleReconciliation,
  ViolationReasoning,
} from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rule: RuleReconciliation | null;
  violation: ViolationReasoning | null;
}

type ActionCardState =
  | { kind: "idle" }
  | { kind: "executing" }
  | { kind: "succeeded"; result: ExecutionResult; executed_at: string }
  | { kind: "failed"; error: string };

export function ViolationDetailDialog({
  open,
  onOpenChange,
  rule,
  violation,
}: Props) {
  const [historyByIdx, setHistoryByIdx] = useState<Map<number, ApprovalSummary>>(
    new Map(),
  );

  useEffect(() => {
    if (!open || !violation) {
      setHistoryByIdx(new Map());
      return;
    }
    let cancelled = false;
    getApprovalsByViolation(DEMO_COMPANY_ID, violation.violation_id)
      .then((rows) => {
        if (cancelled) return;
        const newest: Map<number, ApprovalSummary> = new Map();
        for (const r of rows) {
          newest.set(r.action_idx, r);
        }
        setHistoryByIdx(newest);
      })
      .catch(() => {
        // History rehydration is best-effort; ignore failures.
      });
    return () => {
      cancelled = true;
    };
  }, [open, violation]);

  if (!rule || !violation) return null;

  const { reasoning, violation: row, violation_id } = violation;
  const monetary = reasoning.monetary_impact_estimate_eur;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[96vw] sm:max-w-7xl max-h-[92vh] overflow-y-auto">
        <DialogHeader className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="rounded-md bg-muted px-2 py-1 text-xs font-mono">
              {rule.rule_id}
            </span>
            <SeverityBadge severity={rule.severity} />
          </div>
          <DialogTitle className="text-2xl">{rule.rule_name}</DialogTitle>
          <DialogDescription className="text-base leading-relaxed text-foreground">
            {reasoning.explanation}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 md:grid-cols-[1fr_1.1fr] mt-4">
          <section className="space-y-5">
            <DetailBlock label="Likely cause">
              <p className="text-sm leading-relaxed">{reasoning.likely_cause}</p>
            </DetailBlock>

            {monetary !== null && (
              <DetailBlock label="Monetary impact">
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-bold tracking-tight">
                    €
                    {monetary.toLocaleString(undefined, {
                      maximumFractionDigits: 2,
                    })}
                  </span>
                </div>
                {reasoning.monetary_impact_explanation && (
                  <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
                    {reasoning.monetary_impact_explanation}
                  </p>
                )}
              </DetailBlock>
            )}

            <DetailBlock label="Violation row">
              <pre className="overflow-x-auto rounded-md bg-muted/40 p-3 text-xs leading-relaxed">
                {JSON.stringify(row, null, 2)}
              </pre>
            </DetailBlock>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Drafted corrective actions
              </h3>
              <span className="text-xs text-muted-foreground">
                {reasoning.drafted_actions.length} action
                {reasoning.drafted_actions.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="space-y-3">
              {reasoning.drafted_actions.map((action, i) => (
                <ActionCard
                  key={i}
                  action={action}
                  actionIdx={i}
                  violationId={violation_id}
                  history={historyByIdx.get(i)}
                />
              ))}
            </div>
            <Separator className="my-4" />
            <p className="text-center text-xs text-muted-foreground">
              Each system updates only when you approve it.
            </p>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DetailBlock({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </h4>
      {children}
    </div>
  );
}

function ActionCard({
  action,
  actionIdx,
  violationId,
  history,
}: {
  action: DraftedAction;
  actionIdx: number;
  violationId: string;
  history?: ApprovalSummary;
}) {
  const initial: ActionCardState = history
    ? history.status === "succeeded"
      ? {
          kind: "succeeded",
          result: {
            status: "succeeded",
            external_id: history.external_id,
            message: history.message,
            error: null,
          },
          executed_at: history.executed_at,
        }
      : { kind: "failed", error: history.error ?? "Unknown error" }
    : { kind: "idle" };

  const [state, setState] = useState<ActionCardState>(initial);

  // Sync initial state when history changes (e.g. dialog reopen).
  useEffect(() => {
    setState(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history?.approval_id]);

  const onClick = useCallback(async () => {
    setState({ kind: "executing" });
    try {
      const { execution_result } = await approveAction(
        DEMO_COMPANY_ID,
        violationId,
        actionIdx,
      );
      if (execution_result.status === "succeeded") {
        setState({
          kind: "succeeded",
          result: execution_result,
          executed_at: new Date().toISOString(),
        });
      } else {
        setState({
          kind: "failed",
          error: execution_result.error ?? "Action failed without an error message",
        });
      }
    } catch (e) {
      setState({ kind: "failed", error: (e as Error).message });
    }
  }, [actionIdx, violationId]);

  const isExecuting = state.kind === "executing";
  const isSucceeded = state.kind === "succeeded";
  const isFailed = state.kind === "failed";

  return (
    <div
      className={
        "rounded-lg border bg-card p-4 transition " +
        (isSucceeded
          ? "border-emerald-500/40"
          : isFailed
            ? "border-rose-500/40"
            : "hover:border-foreground/20")
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2 flex-1">
          <div className="flex items-center gap-2">
            <SystemBadge system={action.target_system} />
            <span className="text-xs font-mono text-muted-foreground">
              {action.action_type}
            </span>
          </div>
          <p className="text-sm leading-snug">{action.description}</p>
          {Object.keys(action.parameters).length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 pt-1">
              {Object.entries(action.parameters).map(([k, v]) => (
                <span
                  key={k}
                  className="text-xs font-mono text-muted-foreground"
                >
                  {k}=<span className="text-foreground">{v}</span>
                </span>
              ))}
            </div>
          )}
          {isSucceeded && (
            <p className="text-xs text-emerald-700 dark:text-emerald-300 pt-1">
              {state.result.message}
            </p>
          )}
          {isFailed && (
            <p className="text-xs text-rose-700 dark:text-rose-300 pt-1">
              <AlertTriangle className="mr-1 inline h-3 w-3" />
              {state.error}
            </p>
          )}
        </div>
        <Button
          size="sm"
          variant={isSucceeded ? "default" : "outline"}
          disabled={isExecuting || isSucceeded}
          onClick={onClick}
        >
          {isExecuting ? (
            <>
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              Executing…
            </>
          ) : isSucceeded ? (
            <>
              <Check className="mr-1 h-3 w-3" />
              Approved
            </>
          ) : isFailed ? (
            <>
              Retry
              <ChevronRight className="ml-1 h-3 w-3" />
            </>
          ) : (
            <>
              Approve
              <ChevronRight className="ml-1 h-3 w-3" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

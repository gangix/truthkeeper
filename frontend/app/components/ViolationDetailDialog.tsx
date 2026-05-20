"use client";

import { useState } from "react";
import { Check, ChevronRight, Info } from "lucide-react";

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
import type {
  DraftedAction,
  RuleReconciliation,
  ViolationReasoning,
} from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rule: RuleReconciliation | null;
  violation: ViolationReasoning | null;
}

export function ViolationDetailDialog({
  open,
  onOpenChange,
  rule,
  violation,
}: Props) {
  if (!rule || !violation) return null;

  const { reasoning, violation: row } = violation;
  const monetary = reasoning.monetary_impact_estimate_eur;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[92vh] overflow-y-auto">
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
                    €{monetary.toLocaleString(undefined, {
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
                <ActionCard key={i} action={action} />
              ))}
            </div>
            <Separator className="my-4" />
            <Button className="w-full" size="lg" disabled>
              <Check className="mr-2 h-4 w-4" />
              Approve all ({reasoning.drafted_actions.length})
            </Button>
            <p className="text-center text-xs text-muted-foreground">
              Execution wiring lands in the next slice.
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

function ActionCard({ action }: { action: DraftedAction }) {
  const [approved, setApproved] = useState(false);
  return (
    <div className="rounded-lg border bg-card p-4 transition hover:border-foreground/20">
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
                <span key={k} className="text-xs font-mono text-muted-foreground">
                  {k}=<span className="text-foreground">{v}</span>
                </span>
              ))}
            </div>
          )}
        </div>
        <Button
          size="sm"
          variant={approved ? "default" : "outline"}
          disabled={approved}
          onClick={() => setApproved(true)}
        >
          {approved ? (
            <>
              <Check className="mr-1 h-3 w-3" />
              Approved
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

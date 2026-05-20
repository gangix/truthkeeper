"use client";

import { Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OnboardingProposal } from "@/lib/types";

export function ReviewView({
  proposal,
  selection,
  approving,
  onApprove,
}: {
  proposal: OnboardingProposal;
  selection: { entities: Set<string>; rules: Set<string>; vocab: Set<string> };
  approving: boolean;
  onApprove: () => void;
}) {
  const ent = selection.entities.size;
  const rules = selection.rules.size;
  const vocab = selection.vocab.size;
  const disabled = approving || ent === 0 || rules === 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Step 5 — Review &amp; approve</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          You&apos;re approving <strong>{ent}</strong> entit{ent === 1 ? "y" : "ies"},{" "}
          <strong>{rules}</strong> rule{rules === 1 ? "" : "s"}, and{" "}
          <strong>{vocab}</strong> vocabulary term{vocab === 1 ? "" : "s"}. This replaces the
          existing CompanyAgentSpec in Postgres.
        </p>
        <Button size="lg" onClick={onApprove} disabled={disabled}>
          {approving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Approving…
            </>
          ) : (
            <>
              <ShieldCheck className="mr-2 h-4 w-4" />
              Approve and replace spec
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

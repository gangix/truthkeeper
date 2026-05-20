"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OnboardingStepper, type StepperItem } from "@/app/components/OnboardingStepper";
import { DiscoveryView } from "@/app/components/DiscoveryView";
import { ProfilingView } from "@/app/components/ProfilingView";
import { ProposalView } from "@/app/components/ProposalView";
import { ReviewView } from "@/app/components/ReviewView";
import {
  approveOnboarding,
  DEMO_COMPANY_ID,
  streamOnboarding,
} from "@/lib/api";
import type {
  ApprovalRequest,
  OnboardingProposal,
  StageEvent,
} from "@/lib/types";

type StepKey = "connect" | "discovery" | "profiling" | "proposal" | "review";

const STEP_LABELS: Record<StepKey, string> = {
  connect: "Connect",
  discovery: "Discover schemas",
  profiling: "Profile data",
  proposal: "Propose entities + rules",
  review: "Review & approve",
};

const STEP_ORDER: StepKey[] = ["connect", "discovery", "profiling", "proposal", "review"];

export default function OnboardingPage() {
  const router = useRouter();
  const [started, setStarted] = useState(false);
  const [activeStep, setActiveStep] = useState<StepKey>("connect");
  const [discoverySummary, setDiscoverySummary] = useState<string | null>(null);
  const [profilingSummary, setProfilingSummary] = useState<string | null>(null);
  const [proposal, setProposal] = useState<OnboardingProposal | null>(null);
  const [error, setError] = useState<{ stage: string; message: string } | null>(null);
  const [selection, setSelection] = useState<{
    entities: Set<string>;
    rules: Set<string>;
    vocab: Set<string>;
  }>({ entities: new Set(), rules: new Set(), vocab: new Set() });
  const [approving, setApproving] = useState(false);

  const handleEvent = useCallback((event: StageEvent) => {
    if (event.error) {
      setError({ stage: event.stage, message: event.error });
      return;
    }
    if (event.stage === "discovery") {
      const summary = (event.payload as { summary?: string } | null)?.summary ?? "";
      setDiscoverySummary(summary);
      setActiveStep("profiling");
    } else if (event.stage === "profiling") {
      const summary = (event.payload as { summary?: string } | null)?.summary ?? "";
      setProfilingSummary(summary);
      setActiveStep("proposal");
    } else if (event.stage === "synthesis") {
      const p = event.payload as OnboardingProposal;
      setProposal(p);
      setSelection({
        entities: new Set(p.entities.map((e) => e.proposal_id)),
        rules: new Set(p.rules.map((r) => r.proposal_id)),
        vocab: new Set(p.vocabulary.map((v) => v.proposal_id)),
      });
      setActiveStep("review");
    }
  }, []);

  const start = useCallback(() => {
    setStarted(true);
    setActiveStep("discovery");
    setError(null);
    const stop = streamOnboarding(
      DEMO_COMPANY_ID,
      handleEvent,
      (err) => setError({ stage: "stream", message: err.message }),
    );
    return stop;
  }, [handleEvent]);

  useEffect(() => {
    if (!started) return;
    return start();
  }, [started, start]);

  const steps: StepperItem[] = useMemo(() => {
    const statusFor = (key: StepKey) => {
      if (error?.stage === key) return "error" as const;
      const idx = STEP_ORDER.indexOf(key);
      const active = STEP_ORDER.indexOf(activeStep);
      if (idx < active) return "done" as const;
      if (idx === active) return "active" as const;
      return "pending" as const;
    };
    return STEP_ORDER.map((k) => ({ key: k, label: STEP_LABELS[k], status: statusFor(k) }));
  }, [activeStep, error]);

  const onApprove = useCallback(async () => {
    if (!proposal) return;
    setApproving(true);
    setError(null);
    try {
      const body: ApprovalRequest = {
        proposal_id: proposal.proposal_id,
        company_name: "TruthKeeper Demo Co",
        accepted_entity_ids: [...selection.entities],
        accepted_rule_ids: [...selection.rules],
        accepted_vocab_ids: [...selection.vocab],
      };
      await approveOnboarding(DEMO_COMPANY_ID, body);
      router.push("/");
    } catch (e) {
      setError({ stage: "approve", message: (e as Error).message });
    } finally {
      setApproving(false);
    }
  }, [proposal, router, selection]);

  const toggle = useCallback(
    (kind: "entities" | "rules" | "vocab", id: string) => {
      setSelection((prev) => {
        const next = new Set(prev[kind]);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return { ...prev, [kind]: next };
      });
    },
    [],
  );

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            TruthKeeper · Onboarding
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Teach the agent your stack</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Fivetran connectors are already linked. The agent will discover your schemas, profile
            the data, and propose the entities + rules. You approve what survives.
          </p>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-8 px-6 py-10 md:grid-cols-[200px_1fr]">
        <aside>
          <OnboardingStepper steps={steps} />
        </aside>

        <div className="space-y-6">
          {error && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-700 dark:text-rose-300">
              <AlertTriangle className="mr-2 inline h-4 w-4" />
              Failed at {error.stage}: {error.message}
            </div>
          )}

          {!started && (
            <Card>
              <CardHeader>
                <CardTitle>Step 1 — Connect</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Your three Fivetran connectors are already linked: Salesforce, Stripe, HubSpot.
                  Click below to let the agent discover the schemas.
                </p>
                <Button size="lg" onClick={() => setStarted(true)}>
                  <Play className="mr-2 h-4 w-4" />
                  Start onboarding
                </Button>
              </CardContent>
            </Card>
          )}

          {started && (
            <>
              <DiscoveryView summary={discoverySummary} active={activeStep === "discovery"} />
              <ProfilingView summary={profilingSummary} active={activeStep === "profiling"} />
              <ProposalView
                proposal={proposal}
                selection={selection}
                onToggle={toggle}
                active={activeStep === "proposal" || activeStep === "review"}
              />
              {activeStep === "review" && proposal && (
                <ReviewView
                  proposal={proposal}
                  selection={selection}
                  approving={approving}
                  onApprove={onApprove}
                />
              )}
            </>
          )}
        </div>
      </section>
    </main>
  );
}

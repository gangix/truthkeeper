"use client";

import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SeverityBadge, SystemBadge } from "@/lib/badges";
import { ToggleRow } from "@/app/components/ToggleRow";
import type { OnboardingProposal } from "@/lib/types";

export function ProposalView({
  proposal,
  selection,
  onToggle,
  active,
}: {
  proposal: OnboardingProposal | null;
  selection: { entities: Set<string>; rules: Set<string>; vocab: Set<string> };
  onToggle: (kind: "entities" | "rules" | "vocab", id: string) => void;
  active: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Step 4 — Propose entities + rules</CardTitle>
      </CardHeader>
      <CardContent>
        {active && !proposal && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Gemini is synthesizing the entity model + rules…
          </div>
        )}

        {proposal && (
          <div className="space-y-6">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Entities ({proposal.entities.length})
              </p>
              <div className="space-y-2">
                {proposal.entities.map((e) => (
                  <ToggleRow
                    key={e.proposal_id}
                    checked={selection.entities.has(e.proposal_id)}
                    onChange={() => onToggle("entities", e.proposal_id)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">{e.name}</span>
                      <span className="text-xs text-muted-foreground">
                        — {e.mappings.length} system mapping{e.mappings.length === 1 ? "" : "s"}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                      {e.mappings.map((m, i) => (
                        <span key={i} className="flex items-center gap-1">
                          <SystemBadge system={m.system} />
                          <code className="text-muted-foreground">{m.table}.{m.id_field}</code>
                        </span>
                      ))}
                    </div>
                  </ToggleRow>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Rules ({proposal.rules.length})
              </p>
              <div className="space-y-2">
                {proposal.rules.map((r) => (
                  <ToggleRow
                    key={r.proposal_id}
                    checked={selection.rules.has(r.proposal_id)}
                    onChange={() => onToggle("rules", r.proposal_id)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-mono">
                        {r.id}
                      </span>
                      <SeverityBadge severity={r.severity} />
                      <span className="font-semibold text-sm">{r.name}</span>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
                      {r.description}
                    </p>
                  </ToggleRow>
                ))}
              </div>
            </div>

            {proposal.vocabulary.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Vocabulary ({proposal.vocabulary.length})
                </p>
                <div className="space-y-2">
                  {proposal.vocabulary.map((v) => (
                    <ToggleRow
                      key={v.proposal_id}
                      checked={selection.vocab.has(v.proposal_id)}
                      onChange={() => onToggle("vocab", v.proposal_id)}
                    >
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-semibold">{v.canonical}</span>
                        <span className="text-xs text-muted-foreground">
                          aliases: {v.aliases.join(", ") || "—"}
                        </span>
                      </div>
                    </ToggleRow>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

"use client";

import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function DiscoveryView({
  summary,
  active,
}: {
  summary: string | null;
  active: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Step 2 — Discover schemas</CardTitle>
      </CardHeader>
      <CardContent>
        {active && !summary && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Agent is calling Fivetran MCP to list connectors and read schemas…
          </div>
        )}
        {summary && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{summary}</p>
        )}
      </CardContent>
    </Card>
  );
}

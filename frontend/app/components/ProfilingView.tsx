"use client";

import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ProfilingView({
  summary,
  active,
}: {
  summary: string | null;
  active: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Step 3 — Profile data</CardTitle>
      </CardHeader>
      <CardContent>
        {active && !summary && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Agent is profiling categorical columns in BigQuery (DISTINCT values + counts)…
          </div>
        )}
        {summary && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{summary}</p>
        )}
      </CardContent>
    </Card>
  );
}

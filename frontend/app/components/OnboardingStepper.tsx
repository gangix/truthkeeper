"use client";

import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type StepStatus = "pending" | "active" | "done" | "error";

export interface StepperItem {
  key: string;
  label: string;
  status: StepStatus;
}

export function OnboardingStepper({ steps }: { steps: StepperItem[] }) {
  return (
    <ol className="space-y-3">
      {steps.map((s, i) => (
        <li key={s.key} className="flex items-center gap-3">
          <span
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded-full text-xs font-mono",
              s.status === "done" && "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
              s.status === "active" && "bg-amber-500/15 text-amber-700 dark:text-amber-300",
              s.status === "error" && "bg-rose-500/15 text-rose-700 dark:text-rose-300",
              s.status === "pending" && "bg-muted text-muted-foreground",
            )}
          >
            {s.status === "done" ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : s.status === "active" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Circle className="h-3 w-3" />
            )}
          </span>
          <span
            className={cn(
              "text-sm",
              s.status === "active" && "font-semibold",
              s.status === "pending" && "text-muted-foreground",
            )}
          >
            {i + 1}. {s.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

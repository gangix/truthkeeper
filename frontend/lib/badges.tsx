import { Badge } from "@/components/ui/badge";
import type { Severity, SystemName } from "@/lib/types";

const SEVERITY_STYLE: Record<Severity, string> = {
  critical: "border-rose-500/30 bg-rose-500/15 text-rose-700 dark:text-rose-300",
  high: "border-orange-500/30 bg-orange-500/15 text-orange-700 dark:text-orange-300",
  medium: "border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300",
  low: "border-zinc-500/30 bg-zinc-500/15 text-zinc-700 dark:text-zinc-300",
};

const SYSTEM_STYLE: Record<SystemName, string> = {
  stripe: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  salesforce: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  hubspot: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge
      variant="outline"
      className={`uppercase tracking-wider ${SEVERITY_STYLE[severity]}`}
    >
      {severity}
    </Badge>
  );
}

export function SystemBadge({ system }: { system: SystemName }) {
  return (
    <Badge variant="outline" className={`font-mono ${SYSTEM_STYLE[system]}`}>
      {system}
    </Badge>
  );
}

"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function ToggleRow({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: () => void;
  children: ReactNode;
}) {
  return (
    <label
      className={cn(
        "flex w-full cursor-pointer items-start gap-3 rounded-lg border bg-background/60 p-3 transition",
        checked ? "border-foreground/20" : "border-dashed opacity-60",
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="mt-1 h-4 w-4 shrink-0 cursor-pointer"
      />
      <div className="min-w-0 flex-1">{children}</div>
    </label>
  );
}

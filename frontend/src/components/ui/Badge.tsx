import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type Severity = "critical" | "high" | "medium" | "low" | "info" | "ok" | "neutral";

const tone: Record<Severity, string> = {
  critical: "bg-critical/12 text-critical ring-critical/25 shadow-[0_0_16px_-6px_rgb(var(--critical)/0.7)]",
  high: "bg-high/12 text-high ring-high/25",
  medium: "bg-medium/12 text-medium ring-medium/25",
  low: "bg-low/12 text-low ring-low/25",
  info: "bg-info/12 text-info ring-info/25",
  ok: "bg-ok/12 text-ok ring-ok/25 shadow-[0_0_16px_-6px_rgb(var(--ok)/0.7)]",
  neutral: "bg-hairline/[0.06] text-muted ring-hairline/15",
};

const dotTone: Record<Severity, string> = {
  critical: "bg-critical",
  high: "bg-high",
  medium: "bg-medium",
  low: "bg-low",
  info: "bg-info",
  ok: "bg-ok",
  neutral: "bg-muted",
};

export function Badge({
  severity = "info",
  className,
  dot,
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { severity?: Severity; dot?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ring-1 ring-inset",
        tone[severity],
        className,
      )}
      {...props}
    >
      {dot ? (
        <span className={cn("h-1.5 w-1.5 rounded-full", dotTone[severity])} />
      ) : null}
      {children}
    </span>
  );
}

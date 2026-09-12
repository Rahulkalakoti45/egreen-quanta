import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Adds a hover lift + border/glow response. */
  hover?: boolean;
  /** Persistent brand glow — reserve for hero / focal panels. */
  glow?: boolean;
  /** Tighter default padding. */
  compact?: boolean;
  /** Drop the default padding entirely. */
  flush?: boolean;
}

export function Card({ className, hover, glow, compact, flush, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "card relative",
        !flush && (compact ? "p-3" : "p-4 sm:p-5"),
        hover && "card-hover",
        glow && "shadow-glow",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  subtitle,
  actions,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        {subtitle ? <p className="mt-0.5 text-xs text-muted">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

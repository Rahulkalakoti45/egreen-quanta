import type { ReactNode } from "react";

export function EmptyState({
  title,
  hint,
  icon,
  action,
}: {
  title: string;
  hint?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex animate-fade-in flex-col items-center justify-center rounded-2xl border border-dashed border-hairline/12 bg-hairline/[0.015] px-6 py-16 text-center">
      <div className="relative mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-hairline/[0.04] text-muted">
        <span className="absolute inset-0 rounded-2xl bg-primary/10 blur-xl" />
        <span className="relative">
          {icon ?? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-6 w-6" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" strokeLinecap="round" />
            </svg>
          )}
        </span>
      </div>
      <p className="text-sm font-semibold text-fg">{title}</p>
      {hint ? <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-muted">{hint}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/** Placeholder for feature areas delivered in a later build module. */
export function ModulePlaceholder({ module, feature }: { module: string; feature: string }) {
  return (
    <EmptyState
      title={`${feature} arrives in ${module}`}
      hint="This screen is wired into routing and the design system now; its data and interactions land with that build module."
    />
  );
}

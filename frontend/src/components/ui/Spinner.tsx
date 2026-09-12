import { cn } from "@/lib/cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
    />
  );
}

/** Full-pane loading state with an orbiting quantum-ish mark. */
export function LoadingPane({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20 text-sm text-muted">
      <span className="relative grid h-10 w-10 place-items-center">
        <span className="absolute inset-0 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
        <span
          className="absolute inset-1.5 animate-spin rounded-full border-2 border-accent/20 border-b-accent"
          style={{ animationDirection: "reverse", animationDuration: "1.6s" }}
        />
        <span className="h-1.5 w-1.5 rounded-full bg-primary shadow-glow-sm" />
      </span>
      <span className="tracking-wide">{label}…</span>
    </div>
  );
}

/** Shimmer block for skeleton states. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-shimmer rounded-lg", className)} />;
}

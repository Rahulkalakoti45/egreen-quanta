import { cn } from "@/lib/cn";

export function TabBar<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: readonly (readonly [T, string])[];
  value: T;
  onChange: (t: T) => void;
}) {
  return (
    <div className="mb-5 flex gap-1 border-b border-hairline/10">
      {tabs.map(([id, label]) => {
        const on = id === value;
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            className={cn(
              "relative -mb-px px-3.5 py-2.5 text-sm font-medium transition-colors",
              on ? "text-fg" : "text-muted hover:text-fg",
            )}
          >
            {label}
            {on && (
              <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand-gradient shadow-glow-sm" />
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Shared textarea styling matching Input. */
export const textareaClass =
  "w-full rounded-lg border border-hairline/10 bg-hairline/[0.03] px-3 py-2 font-mono text-xs text-fg outline-none " +
  "transition-all placeholder:text-faint focus:border-primary/50 focus:ring-4 focus:ring-primary/10";

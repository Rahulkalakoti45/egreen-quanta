import { useTheme, type Theme } from "@/lib/theme";
import { cn } from "@/lib/cn";

const OPTIONS: { value: Theme; label: string; icon: string }[] = [
  { value: "light", label: "Light", icon: "M12 3v2M12 19v2M5 12H3M21 12h-2M6 6 4.5 4.5M18 18l1.5 1.5M6 18l-1.5 1.5M18 6l1.5-1.5M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" },
  { value: "system", label: "System", icon: "M4 5h16v10H4zM8 19h8M12 15v4" },
  { value: "dark", label: "Dark", icon: "M20 13a8 8 0 1 1-9-9 6 6 0 0 0 9 9Z" },
];

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  return (
    <div
      className="flex items-center rounded-xl border border-hairline/10 bg-hairline/[0.03] p-0.5"
      role="group"
      aria-label="Theme"
    >
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          onClick={() => setTheme(o.value)}
          aria-pressed={theme === o.value}
          aria-label={o.label}
          title={o.label}
          className={cn(
            "grid h-7 w-7 place-items-center rounded-lg transition-all duration-200",
            theme === o.value
              ? "bg-hairline/[0.09] text-primary shadow-inner-top"
              : "text-muted hover:text-fg",
          )}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} className="h-[14px] w-[14px]" aria-hidden="true">
            <path d={o.icon} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      ))}
    </div>
  );
}

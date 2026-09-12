import { NavLink } from "react-router-dom";

import { Drawer } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";

import { NAV_ITEMS } from "./navigation";

function Icon({ path }: { path: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[18px] w-[18px] shrink-0"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

function Brand() {
  return (
    <div className="mb-7 flex items-center gap-2.5 px-1.5">
      <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-brand-gradient text-primary-fg shadow-glow-sm">
        <span className="absolute inset-0 rounded-xl bg-brand-gradient blur-md opacity-60" />
        <svg viewBox="0 0 24 24" fill="none" className="relative h-5 w-5" aria-hidden="true">
          <path
            d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4Z"
            stroke="currentColor"
            strokeWidth={1.8}
          />
          <circle cx="12" cy="11" r="2.5" stroke="currentColor" strokeWidth={1.8} />
        </svg>
      </div>
      <div className="leading-tight">
        <div className="font-display text-[15px] font-semibold tracking-tight text-fg">
          Egreen Quanta
        </div>
        <div className="text-[9.5px] font-medium uppercase tracking-[0.22em] text-muted">
          Quantum SOC
        </div>
      </div>
    </div>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const { atLeast } = useAuth();
  const items = NAV_ITEMS.filter((i) => {
    if (i.to === "/admin") return atLeast("admin");
    if (i.to === "/audit") return atLeast("auditor");
    return true;
  });

  return (
    <nav className="flex flex-col gap-1" aria-label="Primary">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60",
              isActive
                ? "bg-hairline/[0.06] font-medium text-fg"
                : "text-muted hover:bg-hairline/[0.04] hover:text-fg",
            )
          }
        >
          {({ isActive }) => (
            <>
              <span
                className={cn(
                  "absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-brand-gradient transition-all duration-300",
                  isActive ? "opacity-100 shadow-glow-sm" : "opacity-0",
                )}
              />
              <span
                className={cn(
                  "transition-colors",
                  isActive ? "text-primary" : "text-muted group-hover:text-fg",
                )}
              >
                <Icon path={item.icon} />
              </span>
              <span className="flex-1">{item.label}</span>
              {item.module ? (
                <span className="rounded bg-hairline/[0.06] px-1.5 text-[9px] font-semibold tracking-wide text-faint opacity-0 transition-opacity group-hover:opacity-100">
                  {item.module}
                </span>
              ) : null}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="glass sticky top-0 hidden h-screen w-60 shrink-0 flex-col rounded-none border-y-0 border-l-0 border-r border-hairline/10 px-3.5 py-5 md:flex">
      <Brand />
      <NavList />
      <div className="mt-auto space-y-2 px-1.5 pt-4">
        <div className="hairline" />
        <div className="flex items-center gap-1.5 text-[10px] font-medium text-faint">
          <span className="h-1 w-1 rounded-full bg-ok animate-pulse-glow" />
          v0.1.0 · PS-141 · SIH 2026
        </div>
      </div>
    </aside>
  );
}

export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Drawer open={open} onClose={onClose} title="Navigation" width="16rem" side="left">
      <NavList onNavigate={onClose} />
    </Drawer>
  );
}

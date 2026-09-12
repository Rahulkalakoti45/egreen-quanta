import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import type { SystemInfo } from "@/types/api";

import { ThemeToggle } from "./ThemeToggle";

export function Topbar({
  onMenu,
  streamConnected,
}: {
  onMenu?: () => void;
  streamConnected?: boolean;
}) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const { data } = useQuery({
    queryKey: ["system-info"],
    queryFn: () => api.get<SystemInfo>("/system/info"),
    staleTime: 60_000,
  });

  return (
    <header className="glass sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between rounded-none border-x-0 border-t-0 border-b border-hairline/10 px-4 sm:px-6">
      <div className="flex items-center gap-3 text-xs">
        {onMenu && (
          <button
            onClick={onMenu}
            aria-label="Open navigation"
            className="grid h-8 w-8 place-items-center rounded-lg border border-hairline/10 bg-hairline/[0.04] text-muted md:hidden"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
            </svg>
          </button>
        )}
        <span className="flex items-center gap-2 rounded-full border border-hairline/10 bg-hairline/[0.03] px-2.5 py-1 text-muted">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-ok" />
          </span>
          {data ? (
            <>
              <span className="hidden sm:inline">API online ·</span>
              <span className="font-medium text-fg">{data.environment}</span>
              <span className="text-faint">·</span>
              <span className="font-mono text-[11px]">{data.database}</span>
            </>
          ) : (
            "connecting…"
          )}
        </span>
        {data?.ml_enabled ? <Badge severity="info" dot>ML</Badge> : null}
        <span
          className="hidden items-center gap-1.5 text-faint sm:inline-flex"
          title={streamConnected ? "Live updates connected" : "Live updates offline"}
        >
          <span
            className={cn(
              "inline-block h-1.5 w-1.5 rounded-full",
              streamConnected ? "bg-accent animate-pulse-glow" : "bg-faint",
            )}
          />
          {streamConnected ? "live" : "offline"}
        </span>
      </div>

      <div className="relative flex items-center gap-3 text-xs">
        <span className="hidden text-faint lg:inline">
          revocation {data?.outbound_revocation ? "online" : "offline"}
        </span>
        <ThemeToggle />
        {user && (
          <>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className="flex items-center gap-2 rounded-xl border border-hairline/10 bg-hairline/[0.03] py-1 pl-1 pr-2.5 transition-colors hover:border-hairline/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
            >
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-gradient text-[11px] font-bold text-primary-fg">
                {user.full_name?.[0]?.toUpperCase() ?? user.email[0]?.toUpperCase()}
              </span>
              <span className="hidden max-w-[14ch] truncate text-fg sm:inline">{user.email}</span>
              <Badge severity="neutral">{user.role}</Badge>
            </button>
            {menuOpen && (
              <div
                role="menu"
                className="glass-strong absolute right-0 top-12 z-40 w-52 animate-scale-in rounded-xl p-1.5"
                onMouseLeave={() => setMenuOpen(false)}
              >
                <div className="px-2.5 py-2 text-[11px] text-muted">
                  Signed in as
                  <div className="truncate font-medium text-fg">{user.email}</div>
                </div>
                <div className="hairline my-1" />
                <button
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    void logout();
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-fg transition-colors hover:bg-hairline/[0.06]"
                >
                  <svg viewBox="0 0 24 24" className="h-4 w-4 text-muted" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden="true">
                    <path d="M15 12H3m0 0 4-4m-4 4 4 4M9 5V4a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2h-6a2 2 0 0 1-2-2v-1" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Sign out
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </header>
  );
}

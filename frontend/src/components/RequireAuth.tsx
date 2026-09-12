import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { LoadingPane } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/types/api";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <LoadingPane label="Restoring session…" />;
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function RequireRole({
  atLeast,
  children,
}: {
  atLeast: Role;
  children: ReactNode;
}) {
  const { atLeast: hasAtLeast, status } = useAuth();
  if (status === "loading") return <LoadingPane />;
  if (!hasAtLeast(atLeast)) {
    return (
      <div className="glass mx-auto max-w-sm rounded-2xl p-8 text-center">
        <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-xl bg-critical/12 text-critical">
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
            <rect x="5" y="11" width="14" height="10" rx="2" />
            <path d="M8 11V7a4 4 0 0 1 8 0v4" />
          </svg>
        </div>
        <p className="text-sm font-semibold text-fg">Access restricted</p>
        <p className="mt-1 text-xs text-muted">
          This area requires the <span className="font-medium text-fg">{atLeast}</span> role or higher.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}

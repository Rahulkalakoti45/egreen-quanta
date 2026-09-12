import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/cn";

import type { Severity } from "./Badge";

interface Toast {
  id: number;
  title: string;
  body?: string;
  tone: Severity;
}

interface ToastCtx {
  push: (t: Omit<Toast, "id">) => void;
}

const Ctx = createContext<ToastCtx | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);

  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = ++seq.current;
    setToasts((cur) => [...cur.slice(-3), { ...t, id }]);
    setTimeout(() => setToasts((cur) => cur.filter((x) => x.id !== id)), 6000);
  }, []);

  const value = useMemo(() => ({ push }), [push]);

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[70] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={cn(
              "glass-strong pointer-events-auto flex animate-fade-up gap-3 rounded-xl p-3 text-sm",
              t.tone === "critical"
                ? "border-critical/40 shadow-[0_0_30px_-10px_rgb(var(--critical)/0.6)]"
                : t.tone === "high"
                  ? "border-high/40"
                  : t.tone === "ok"
                    ? "border-ok/40 shadow-[0_0_30px_-10px_rgb(var(--ok)/0.6)]"
                    : "border-hairline/12",
            )}
          >
            <span
              className={cn(
                "mt-0.5 h-2 w-2 shrink-0 rounded-full",
                t.tone === "critical"
                  ? "bg-critical"
                  : t.tone === "high"
                    ? "bg-high"
                    : t.tone === "ok"
                      ? "bg-ok"
                      : "bg-primary",
              )}
            />
            <div className="min-w-0">
              <p className="font-semibold text-fg">{t.title}</p>
              {t.body ? <p className="mt-0.5 text-xs text-muted">{t.body}</p> : null}
            </div>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

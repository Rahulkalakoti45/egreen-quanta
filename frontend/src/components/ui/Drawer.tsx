import { useEffect, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Drawer({
  open,
  onClose,
  title,
  children,
  width = "32rem",
  side = "right",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  width?: string;
  side?: "left" | "right";
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex animate-fade-in bg-black/60 backdrop-blur-sm",
        side === "right" ? "justify-end" : "justify-start",
      )}
      onMouseDown={onClose}
    >
      <div
        className={cn(
          "glass-strong flex h-full flex-col rounded-none",
          side === "right"
            ? "border-y-0 border-r-0 border-l border-hairline/12"
            : "border-y-0 border-l-0 border-r border-hairline/12",
        )}
        style={{
          width,
          animation: `${side === "right" ? "slide-in-right" : "slide-in-left"} 0.3s cubic-bezier(0.22,1,0.36,1) both`,
        }}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex items-center justify-between border-b border-hairline/10 px-4 py-3">
          <h2 className="font-display text-sm font-semibold text-fg">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="grid h-7 w-7 place-items-center rounded-lg text-muted transition-colors hover:bg-hairline/[0.08] hover:text-fg"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
      </div>
      <style>{`
        @keyframes slide-in-right { from { transform: translateX(100%); } to { transform: none; } }
        @keyframes slide-in-left { from { transform: translateX(-100%); } to { transform: none; } }
      `}</style>
    </div>
  );
}

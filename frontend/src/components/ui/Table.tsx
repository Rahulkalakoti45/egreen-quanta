import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Table({ head, children }: { head: ReactNode; children: ReactNode }) {
  return (
    <div className="glass overflow-x-auto rounded-2xl">
      <table className="w-full min-w-[40rem] text-sm">
        <thead className="border-b border-hairline/10 bg-hairline/[0.03] text-left text-[11px] uppercase tracking-wide text-muted">
          <tr>{head}</tr>
        </thead>
        <tbody className="divide-y divide-hairline/[0.06]">{children}</tbody>
      </table>
    </div>
  );
}

export function Th({ children, className }: { children?: ReactNode; className?: string }) {
  return (
    <th className={cn("whitespace-nowrap px-3.5 py-2.5 font-semibold", className)}>{children}</th>
  );
}

export function Td({ children, className }: { children?: ReactNode; className?: string }) {
  return (
    <td className={cn("whitespace-nowrap px-3.5 py-2.5 text-fg/90", className)}>{children}</td>
  );
}

/** Wrap <tr> rows with this class via the `className` on your own <tr> for hover. */
export const rowHover =
  "transition-colors hover:bg-hairline/[0.04] focus-within:bg-hairline/[0.04]";

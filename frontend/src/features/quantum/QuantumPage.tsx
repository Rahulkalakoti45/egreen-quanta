import { useState } from "react";

import { PageHeader } from "@/components/ui";
import { cn } from "@/lib/cn";

import { CorrelationPanel } from "./CorrelationPanel";
import { MigrationPlanPanel } from "./MigrationPlanPanel";
import { QuantumRiskPanel } from "./QuantumRiskPanel";
import { TuningPanel } from "./TuningPanel";

type Tab = "risk" | "plan" | "tuning" | "correlation";

const TABS: { id: Tab; label: string; blurb: string; icon: string }[] = [
  {
    id: "risk",
    label: "Quantum risk",
    blurb: "Score keys for Shor/Grover exposure",
    icon: "M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4Z",
  },
  {
    id: "plan",
    label: "Migration plan",
    blurb: "Sequence PQC rollout waves",
    icon: "M4 20h16M4 4v16M8 16V8m4 8V4m4 12v-6",
  },
  {
    id: "tuning",
    label: "Detection tuning",
    blurb: "Anneal rule weights for max F1",
    icon: "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6",
  },
  {
    id: "correlation",
    label: "Correlation",
    blurb: "Cluster events into incidents",
    icon: "M12 12m-9 0a9 9 0 1 0 18 0 9 9 0 1 0-18 0M12 3v4m0 10v4M3 12h4m10 0h4",
  },
];

export function QuantumPage() {
  const [tab, setTab] = useState<Tab>("risk");
  const active = TABS.find((t) => t.id === tab)!;

  return (
    <>
      <PageHeader
        eyebrow="Quantum-inspired optimisation"
        title="Quantum Lab"
        description="Classical simulated / simulated-quantum annealing over QUBO models — no quantum hardware. Every run is seeded; small instances are brute-force-verified."
      />

      <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {TABS.map((t) => {
          const on = t.id === tab;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "group relative overflow-hidden rounded-xl border p-3 text-left transition-all duration-200",
                on
                  ? "border-primary/40 bg-primary/[0.07] shadow-glow-sm"
                  : "border-hairline/10 bg-hairline/[0.02] hover:border-hairline/20 hover:bg-hairline/[0.04]",
              )}
            >
              {on && (
                <span className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent" />
              )}
              <span
                className={cn(
                  "inline-flex h-7 w-7 items-center justify-center rounded-lg transition-colors",
                  on ? "bg-brand-gradient text-primary-fg" : "bg-hairline/[0.06] text-muted",
                )}
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.7} aria-hidden="true">
                  <path d={t.icon} strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <div className={cn("mt-2 text-sm font-semibold", on ? "text-fg" : "text-muted group-hover:text-fg")}>
                {t.label}
              </div>
              <div className="mt-0.5 hidden text-[11px] leading-tight text-faint sm:block">
                {t.blurb}
              </div>
            </button>
          );
        })}
      </div>

      <div key={tab} className="animate-fade-up">
        <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-wide text-faint">
          <span className="h-1 w-1 rounded-full bg-primary" />
          {active.blurb}
        </div>
        {tab === "risk" && <QuantumRiskPanel />}
        {tab === "plan" && <MigrationPlanPanel />}
        {tab === "tuning" && <TuningPanel />}
        {tab === "correlation" && <CorrelationPanel />}
      </div>
    </>
  );
}

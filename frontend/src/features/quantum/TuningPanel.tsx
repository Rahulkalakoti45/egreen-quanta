import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button, Card } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { useCountUp } from "@/lib/motion";
import type { TuningMetrics, TuningResult } from "@/types/api";

import { AnnealingField } from "./lab/AnnealingField";
import { EnergyChart } from "./EnergyChart";

function MetricArc({ label, before, after }: { label: string; before: number; after: number }) {
  const shown = useCountUp(after, 1100, 3);
  const delta = after - before;
  const pct = Math.round(Math.min(1, Math.max(0, after)) * 100);
  const R = 30;
  const C = 2 * Math.PI * R;

  return (
    <div className="flex flex-col items-center rounded-xl border border-hairline/10 bg-hairline/[0.02] p-3">
      <div className="relative grid h-20 w-20 place-items-center">
        <svg viewBox="0 0 72 72" className="h-20 w-20 -rotate-90">
          <circle cx="36" cy="36" r={R} fill="none" stroke="rgb(var(--hairline) / 0.08)" strokeWidth="6" />
          <circle
            cx="36"
            cy="36"
            r={R}
            fill="none"
            stroke="rgb(var(--primary))"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={C}
            strokeDashoffset={C * (1 - Math.min(1, Math.max(0, shown)))}
            style={{ transition: "stroke-dashoffset 0.2s linear", filter: "drop-shadow(0 0 6px rgb(var(--primary) / 0.5))" }}
          />
        </svg>
        <span className="absolute font-mono text-sm font-semibold text-fg tabular-nums">{pct}%</span>
      </div>
      <div className="mt-2 text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 flex items-center gap-1 text-[11px]">
        <span className="font-mono text-faint tabular-nums">{before.toFixed(3)}</span>
        <span className="text-faint">→</span>
        <span className={cn("font-mono font-semibold tabular-nums", delta >= 0 ? "text-ok" : "text-critical")}>
          {after.toFixed(3)}
        </span>
      </div>
    </div>
  );
}

export function TuningPanel() {
  const qc = useQueryClient();
  const { atLeast } = useAuth();

  const run = useMutation<TuningResult, ApiError>({
    mutationFn: () => api.post<TuningResult>("/quantum/tuning/run", { synthetic: true, seed: 1337 }),
  });
  const apply = useMutation<{ applied: number }, ApiError, string>({
    mutationFn: (runId) => api.post("/quantum/tuning/apply", { run_id: runId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["detection-rules"] }),
  });

  const r = run.data;
  const m = (k: keyof TuningMetrics) => [r?.before[k] ?? 0, r?.after[k] ?? 0] as const;
  const maxW = r ? Math.max(...Object.values(r.weights), 1) : 1;

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-fg">
          Tune detection-rule weights against labelled history — QUBO over discrete weight levels
        </span>
        <Button onClick={() => run.mutate()} loading={run.isPending}>
          {run.isPending ? "Optimising" : "Run tuning"}
        </Button>
        {run.error && <span className="text-xs text-critical">{run.error.message}</span>}
      </Card>

      {r && (
        <>
          <Card>
            <p className="mb-3 text-xs text-muted">
              {r.sample_size} labelled events ({r.source}) · decision threshold {r.threshold}
            </p>
            <div className="grid grid-cols-3 gap-3">
              <MetricArc label="Precision" before={m("precision")[0]} after={m("precision")[1]} />
              <MetricArc label="Recall" before={m("recall")[0]} after={m("recall")[1]} />
              <MetricArc label="F1" before={m("f1")[0]} after={m("f1")[1]} />
            </div>
          </Card>

          <Card>
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
              Proposed weights · levels {r.levels.join(", ")}
            </h4>
            <div className="space-y-1.5">
              {Object.entries(r.weights)
                .sort((a, b) => b[1] - a[1])
                .map(([code, w], i) => (
                  <div key={code} className="flex items-center gap-2 text-xs">
                    <span className="w-12 font-mono text-muted">{code}</span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-hairline/10">
                      <span
                        className="block h-full rounded-full bg-brand-gradient animate-fade-in"
                        style={{ width: `${(w / maxW) * 100}%`, animationDelay: `${i * 40}ms` }}
                      />
                    </span>
                    <span className="w-6 text-right font-mono font-semibold text-primary tabular-nums">
                      {w}
                    </span>
                  </div>
                ))}
            </div>
            {atLeast("admin") && (
              <Button
                size="sm"
                className="mt-4"
                disabled={apply.isPending}
                onClick={() => apply.mutate(r.run_id)}
              >
                {apply.isPending
                  ? "Applying…"
                  : apply.data
                    ? `Applied to ${apply.data.applied} rules`
                    : "Apply these weights"}
              </Button>
            )}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">
                Annealing over the weight QUBO
              </h4>
              <AnnealingField solver={r.solver} />
            </Card>
            <Card>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                Solver convergence
              </h4>
              <EnergyChart solver={r.solver} />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Button, Card } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { axisTick, tooltipStyle } from "@/lib/chart";
import { cn } from "@/lib/cn";
import type { MigrationPlanResult, MigrationWaveMember } from "@/types/api";

import { AnnealingField } from "./lab/AnnealingField";
import { EnergyChart } from "./EnergyChart";

const SEED_IDENTITIES = [
  { name: "root-ca", qes: 96, criticality: 5, effort: 3 },
  { name: "issuing-ca", qes: 88, criticality: 5, effort: 3 },
  { name: "code-signing", qes: 82, criticality: 4, effort: 2 },
  { name: "tls-frontend", qes: 74, criticality: 4, effort: 2 },
  { name: "email-smime", qes: 61, criticality: 3, effort: 2 },
  { name: "doc-signing", qes: 58, criticality: 3, effort: 2 },
  { name: "device-attest", qes: 44, criticality: 2, effort: 1 },
  { name: "ci-artifacts", qes: 39, criticality: 2, effort: 1 },
  { name: "legacy-app", qes: 30, criticality: 1, effort: 1 },
  { name: "sandbox", qes: 18, criticality: 1, effort: 1 },
];

function waveColor(q: number) {
  if (q >= 75) return "rgb(var(--critical))";
  if (q >= 50) return "rgb(var(--medium))";
  if (q >= 25) return "rgb(var(--low))";
  return "rgb(var(--ok))";
}

export function MigrationPlanPanel() {
  const [waves, setWaves] = useState(4);
  const plan = useMutation<MigrationPlanResult, ApiError>({
    mutationFn: () =>
      api.post<MigrationPlanResult>("/quantum/pq-risk/plan", {
        identities: SEED_IDENTITIES,
        waves,
        seed: 1337,
      }),
  });

  const p = plan.data;

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-fg">
          Sequence a PQC migration for{" "}
          <span className="font-semibold">{SEED_IDENTITIES.length} signing identities</span> over
        </span>
        <select
          value={waves}
          onChange={(e) => setWaves(Number(e.target.value))}
          className="cursor-pointer rounded-lg border border-hairline/10 bg-hairline/[0.04] px-2.5 py-1.5 text-sm text-fg [&>option]:bg-surface"
        >
          {[3, 4, 5, 6].map((n) => (
            <option key={n} value={n}>
              {n} waves
            </option>
          ))}
        </select>
        <Button onClick={() => plan.mutate()} loading={plan.isPending}>
          {plan.isPending ? "Optimising" : "Run planner"}
        </Button>
        {plan.error && <span className="text-xs text-critical">{plan.error.message}</span>}
      </Card>

      {p && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <MetricCard
              label="Risk-exposure-time"
              value={p.cumulative_exposure}
              sub={`greedy baseline ${p.baseline_exposure}`}
              accent
            />
            <MetricCard
              label="Improvement vs greedy"
              value={`${p.improvement_pct >= 0 ? "−" : "+"}${Math.abs(p.improvement_pct)}%`}
              sub="lower exposure is better"
              tone={p.improvement_pct >= 0 ? "ok" : "critical"}
            />
            <MetricCard
              label="Wave capacity"
              value={`${p.wave_capacity}`}
              sub="effort units per wave"
            />
          </div>

          {p.notes.length > 0 && (
            <Card compact className="border-medium/25 bg-medium/[0.05]">
              {p.notes.map((n) => (
                <p key={n} className="text-[11px] text-medium">
                  {n}
                </p>
              ))}
            </Card>
          )}

          <Card>
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
              Migration timeline
            </h4>
            <MigrationTimeline waves={p.waves} capacity={p.wave_capacity} />
          </Card>

          <ExposureCurve waves={p.waves} />

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">
                Annealing over the ordering QUBO
              </h4>
              <AnnealingField solver={p.solver} />
            </Card>
            <Card>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                Solver convergence
              </h4>
              <EnergyChart solver={p.solver} />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  accent,
  tone,
}: {
  label: string;
  value: string | number;
  sub: string;
  accent?: boolean;
  tone?: "ok" | "critical";
}) {
  return (
    <Card compact className="animate-fade-up">
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div
        className={cn(
          "mt-1 font-display text-2xl font-semibold tabular-nums",
          tone === "ok" && "text-ok",
          tone === "critical" && "text-critical",
          accent && "text-gradient",
          !tone && !accent && "text-fg",
        )}
      >
        {value}
      </div>
      <div className="mt-0.5 text-[11px] text-faint">{sub}</div>
    </Card>
  );
}

function MigrationTimeline({
  waves,
  capacity,
}: {
  waves: MigrationWaveMember[][];
  capacity: number;
}) {
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-[36rem] gap-3">
        {waves.map((members, i) => {
          const load = members.reduce((s, m) => s + m.effort, 0);
          return (
            <div key={i} className="flex-1">
              <div className="relative mb-2 flex items-center gap-2">
                <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-gradient text-[11px] font-bold text-primary-fg">
                  {i + 1}
                </span>
                <span className="text-xs font-semibold text-fg">Wave {i + 1}</span>
                <span className="ml-auto font-mono text-[10px] text-muted">
                  {load}/{capacity}
                </span>
                {i < waves.length - 1 && (
                  <span className="absolute -right-3 top-1/2 h-px w-3 -translate-y-1/2 bg-hairline/20" />
                )}
              </div>
              <span className="mb-2 block h-1 overflow-hidden rounded-full bg-hairline/10">
                <span
                  className="block h-full rounded-full bg-primary/70"
                  style={{ width: `${Math.min(100, (load / capacity) * 100)}%` }}
                />
              </span>
              <div className="space-y-1.5">
                {members.map((m, j) => {
                  const c = waveColor(m.qes);
                  return (
                    <div
                      key={m.name}
                      className="animate-fade-up rounded-lg border p-2"
                      style={{
                        background: `linear-gradient(120deg, ${c}1a, transparent)`,
                        borderColor: `${c}3a`,
                        animationDelay: `${(i * 3 + j) * 50}ms`,
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="truncate text-[11px] font-medium text-fg">{m.name}</span>
                        <span className="font-mono text-[11px] font-semibold" style={{ color: c }}>
                          {m.qes}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-1">
                        {Array.from({ length: m.criticality }).map((_, k) => (
                          <span key={k} className="h-1 w-1 rounded-full" style={{ background: c }} />
                        ))}
                        <span className="ml-auto text-[9px] text-faint">effort {m.effort}</span>
                      </div>
                    </div>
                  );
                })}
                {members.length === 0 && (
                  <p className="rounded-lg border border-dashed border-hairline/12 py-3 text-center text-[11px] text-faint">
                    idle
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Cumulative risk-exposure-time as each wave completes — QUBO order vs a
 *  greedy "smallest effort first" baseline. Illustrative model over the real
 *  wave assignments. */
function ExposureCurve({ waves }: { waves: MigrationWaveMember[][] }) {
  const data = useMemo(() => {
    const all = waves.flat();
    const risk = (m: MigrationWaveMember) => m.qes * m.criticality;
    const totalRisk = all.reduce((s, m) => s + risk(m), 0);

    const greedyOrder = [...all].sort((a, b) => a.effort - b.effort || b.qes - a.qes);
    const perWave = Math.ceil(all.length / Math.max(1, waves.length)) || 1;

    let quboRemaining = totalRisk;
    let greedyRemaining = totalRisk;
    let quboExp = 0;
    let greedyExp = 0;
    const rows: { wave: string; qubo: number; greedy: number }[] = [
      { wave: "start", qubo: 0, greedy: 0 },
    ];
    for (let w = 0; w < waves.length; w++) {
      quboRemaining -= waves[w].reduce((s, m) => s + risk(m), 0);
      const gSlice = greedyOrder.slice(w * perWave, (w + 1) * perWave);
      greedyRemaining -= gSlice.reduce((s, m) => s + risk(m), 0);
      quboExp += Math.max(0, quboRemaining);
      greedyExp += Math.max(0, greedyRemaining);
      rows.push({
        wave: `W${w + 1}`,
        qubo: Math.round(quboExp),
        greedy: Math.round(greedyExp),
      });
    }
    return rows;
  }, [waves]);

  return (
    <Card>
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Cumulative exposure — QUBO vs greedy
        </h4>
        <div className="flex gap-3 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-primary" /> QUBO
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-faint" /> greedy
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ left: -14, right: 8, top: 6 }}>
          <defs>
            <linearGradient id="quboFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgb(var(--primary))" stopOpacity={0.3} />
              <stop offset="100%" stopColor="rgb(var(--primary))" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="wave" tick={{ ...axisTick, fontSize: 10 }} stroke="rgb(var(--border))" />
          <YAxis tick={{ ...axisTick, fontSize: 10 }} width={48} stroke="rgb(var(--border))" />
          <Tooltip contentStyle={tooltipStyle} />
          <Area
            type="monotone"
            dataKey="greedy"
            stroke="rgb(var(--faint))"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            fill="none"
            animationDuration={900}
          />
          <Area
            type="monotone"
            dataKey="qubo"
            stroke="rgb(var(--primary))"
            strokeWidth={2}
            fill="url(#quboFill)"
            animationDuration={1200}
          />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}

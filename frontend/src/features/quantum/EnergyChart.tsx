import {
  Area,
  AreaChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { axisTick, tooltipStyle } from "@/lib/chart";
import type { SolverInfo } from "@/types/api";

export function EnergyChart({ solver }: { solver: SolverInfo }) {
  const data = solver.energy_trajectory.map((e, i) => ({ sweep: i, energy: e }));
  const min = Math.min(...solver.energy_trajectory);

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        <Stat label="method" value={solver.method} />
        <Stat label="best energy" value={solver.best_energy.toFixed(3)} mono accent />
        <Stat label="sweeps" value={solver.sweeps.toLocaleString()} mono />
        <Stat label="seed" value={String(solver.seed)} mono />
        <Stat label="wall" value={`${solver.wall_ms} ms`} mono />
        {solver.optimal != null && (
          <span
            className={
              "inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-[11px] font-medium " +
              (solver.optimal
                ? "border-ok/30 bg-ok/10 text-ok"
                : "border-medium/30 bg-medium/10 text-medium")
            }
          >
            <span className={"h-1.5 w-1.5 rounded-full " + (solver.optimal ? "bg-ok" : "bg-medium")} />
            {solver.optimal
              ? "optimal · brute-force verified"
              : `gap ${solver.optimality_gap ?? "—"}`}
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={210}>
        <AreaChart data={data} margin={{ left: -12, right: 10, top: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="energyFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgb(var(--primary))" stopOpacity={0.35} />
              <stop offset="100%" stopColor="rgb(var(--primary))" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="energyStroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="rgb(var(--primary))" />
              <stop offset="100%" stopColor="rgb(var(--accent))" />
            </linearGradient>
          </defs>
          <XAxis dataKey="sweep" tick={{ ...axisTick, fontSize: 10 }} stroke="rgb(var(--border))" />
          <YAxis tick={{ ...axisTick, fontSize: 10 }} width={54} stroke="rgb(var(--border))" />
          <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: "rgb(var(--accent) / 0.4)" }} />
          <ReferenceLine
            y={min}
            stroke="rgb(var(--ok) / 0.5)"
            strokeDasharray="4 4"
            label={{ value: "min", fill: "rgb(var(--ok))", fontSize: 10, position: "right" }}
          />
          <Area
            type="monotone"
            dataKey="energy"
            stroke="url(#energyStroke)"
            strokeWidth={2}
            fill="url(#energyFill)"
            animationDuration={1400}
            animationEasing="ease-out"
            dot={false}
            activeDot={{ r: 3, fill: "rgb(var(--accent))" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function Stat({
  label,
  value,
  mono,
  accent,
}: {
  label: string;
  value: string;
  mono?: boolean;
  accent?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-hairline/10 bg-hairline/[0.03] px-2 py-1 text-[11px]">
      <span className="uppercase tracking-wide text-faint">{label}</span>
      <span
        className={
          (mono ? "font-mono " : "") +
          (accent ? "text-primary font-semibold" : "text-fg") +
          " tabular-nums"
        }
      >
        {value}
      </span>
    </span>
  );
}

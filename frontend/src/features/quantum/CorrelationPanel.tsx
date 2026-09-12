import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { Button, Card } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { CorrelationResult } from "@/types/api";

const CLUSTER_COLORS = [
  "var(--primary)",
  "var(--accent)",
  "var(--accent-2)",
  "var(--ok)",
  "var(--low)",
  "var(--high)",
];

export function CorrelationPanel() {
  const run = useMutation<CorrelationResult, ApiError>({
    mutationFn: () =>
      api.post<CorrelationResult>("/quantum/correlation/run", { lookback_hours: 24, seed: 1337 }),
  });

  const r = run.data;
  const better = r ? r.qubo_modularity >= r.baseline_modularity : false;

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-fg">
          Re-cluster the last 24h of events with a densest-subgraph QUBO and compare to the greedy
          baseline
        </span>
        <Button onClick={() => run.mutate()} loading={run.isPending}>
          {run.isPending ? "Solving" : "Run correlation"}
        </Button>
        {run.error && <span className="text-xs text-critical">{run.error.message}</span>}
      </Card>

      {r && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Events" value={r.event_count} sub={`${r.clusters.length} incidents · ${r.singletons.length} loose`} />
            <Stat
              label="QUBO modularity"
              value={r.qubo_modularity}
              sub={`baseline ${r.baseline_modularity}`}
              tone={better ? "ok" : "medium"}
            />
            <Stat
              label="Δ modularity"
              value={`${better ? "+" : ""}${(r.qubo_modularity - r.baseline_modularity).toFixed(3)}`}
              sub={better ? "denser communities" : "no gain"}
              tone={better ? "ok" : "medium"}
            />
          </div>

          <Card>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
              Event correlation graph
            </h4>
            <ClusterGraph clusters={r.clusters} singletons={r.singletons} density={r.cluster_density} />
          </Card>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {r.clusters.map((members, i) => (
              <Card key={i} compact className="animate-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1.5 font-semibold text-fg">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: `rgb(${CLUSTER_COLORS[i % CLUSTER_COLORS.length]})` }}
                    />
                    Incident {i + 1}
                  </span>
                  <span className="font-mono text-muted">density {r.cluster_density[i]}</span>
                </div>
                <ul className="space-y-0.5 text-[11px] text-fg/90">
                  {members.map((label, j) => (
                    <li key={j} className="truncate rounded bg-hairline/[0.04] px-1.5 py-0.5">
                      {label}
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>

          {r.singletons.length > 0 && (
            <Card compact>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
                Unclustered ({r.singletons.length})
              </h4>
              <div className="flex flex-wrap gap-1 text-[11px] text-muted">
                {r.singletons.map((s, i) => (
                  <span key={i} className="rounded bg-hairline/[0.04] px-1.5 py-0.5">
                    {s}
                  </span>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string | number;
  sub: string;
  tone?: "ok" | "medium";
}) {
  return (
    <Card compact className="animate-fade-up">
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div
        className={
          "mt-1 font-display text-2xl font-semibold tabular-nums " +
          (tone === "ok" ? "text-ok" : tone === "medium" ? "text-medium" : "text-fg")
        }
      >
        {value}
      </div>
      <div className="mt-0.5 text-[11px] text-faint">{sub}</div>
    </Card>
  );
}

interface Placed {
  id: string;
  cx: number;
  cy: number;
  ci: number;
  r: number;
}

/** Deterministic constellation layout: clusters on a grid, members on a ring,
 *  singletons along the bottom. Nodes fly in from centre on mount. */
function ClusterGraph({
  clusters,
  singletons,
  density,
}: {
  clusters: string[][];
  singletons: string[];
  density: number[];
}) {
  const W = 760;
  const H = 340;
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    setSettled(false);
    const t = setTimeout(() => setSettled(true), 60);
    return () => clearTimeout(t);
  }, [clusters, singletons]);

  const { nodes, hulls } = useMemo(() => {
    const cols = Math.min(clusters.length, 3) || 1;
    const rows = Math.ceil(clusters.length / cols) || 1;
    const cellW = W / cols;
    const cellH = (H - 70) / rows;
    const placed: Placed[] = [];
    const hullData: { x: number; y: number; r: number; ci: number; density: number }[] = [];

    clusters.forEach((members, ci) => {
      const col = ci % cols;
      const row = Math.floor(ci / cols);
      const cx = cellW * (col + 0.5);
      const cy = cellH * (row + 0.5) + 20;
      const ring = Math.min(cellW, cellH) * 0.32;
      hullData.push({ x: cx, y: cy, r: ring + 26, ci, density: density[ci] ?? 0 });
      members.forEach((id, k) => {
        const ang = (k / members.length) * Math.PI * 2 - Math.PI / 2;
        const jitter = members.length > 6 ? (k % 2 ? 0.7 : 1) : 1;
        placed.push({
          id,
          cx: cx + Math.cos(ang) * ring * jitter,
          cy: cy + Math.sin(ang) * ring * jitter,
          ci,
          r: 5,
        });
      });
    });

    singletons.forEach((id, k) => {
      const per = Math.max(1, Math.floor(W / 90));
      placed.push({
        id,
        cx: 45 + (k % per) * ((W - 90) / Math.max(1, per - 1 || 1)),
        cy: H - 30 + (Math.floor(k / per) % 2 ? 12 : 0),
        ci: -1,
        r: 3.5,
      });
    });

    return { nodes: placed, hulls: hullData };
  }, [clusters, singletons, density]);

  const color = (ci: number) =>
    ci < 0 ? "var(--faint)" : CLUSTER_COLORS[ci % CLUSTER_COLORS.length];

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="min-w-[40rem] w-full" style={{ height: H }}>
        <defs>
          {CLUSTER_COLORS.map((c, i) => (
            <radialGradient key={i} id={`hull-${i}`}>
              <stop offset="0%" stopColor={`rgb(${c})`} stopOpacity={0.14} />
              <stop offset="100%" stopColor={`rgb(${c})`} stopOpacity={0} />
            </radialGradient>
          ))}
        </defs>

        {/* cluster hulls */}
        {hulls.map((h) => (
          <g key={h.ci} style={{ opacity: settled ? 1 : 0, transition: "opacity 0.6s ease 0.3s" }}>
            <circle cx={h.x} cy={h.y} r={h.r} fill={`url(#hull-${h.ci % CLUSTER_COLORS.length})`} />
            <circle
              cx={h.x}
              cy={h.y}
              r={h.r}
              fill="none"
              stroke={`rgb(${color(h.ci)})`}
              strokeOpacity={0.25}
              strokeDasharray="3 5"
            />
            <text
              x={h.x}
              y={h.y - h.r - 6}
              textAnchor="middle"
              className="fill-muted font-mono"
              style={{ fontSize: 10 }}
            >
              incident {h.ci + 1} · ρ {h.density}
            </text>
          </g>
        ))}

        {/* edges from each node to its cluster centre */}
        {nodes.map((n, i) => {
          if (n.ci < 0) return null;
          const h = hulls[n.ci];
          return (
            <line
              key={`e-${i}`}
              x1={settled ? n.cx : W / 2}
              y1={settled ? n.cy : H / 2}
              x2={h.x}
              y2={h.y}
              stroke={`rgb(${color(n.ci)})`}
              strokeOpacity={settled ? 0.3 : 0}
              strokeWidth={1}
              style={{ transition: "all 0.7s cubic-bezier(0.22,1,0.36,1)" }}
            />
          );
        })}

        {/* nodes */}
        {nodes.map((n, i) => (
          <g
            key={`n-${i}`}
            style={{
              transform: settled
                ? `translate(${n.cx}px, ${n.cy}px)`
                : `translate(${W / 2}px, ${H / 2}px)`,
              opacity: settled ? 1 : 0,
              transition: `transform 0.7s cubic-bezier(0.22,1,0.36,1) ${Math.min(i * 18, 500)}ms, opacity 0.5s ease ${Math.min(i * 18, 500)}ms`,
            }}
          >
            <circle r={n.r + 4} fill={`rgb(${color(n.ci)})`} opacity={0.15} />
            <circle
              r={n.r}
              fill={`rgb(${color(n.ci)})`}
              style={{ filter: `drop-shadow(0 0 5px rgb(${color(n.ci)} / 0.7))` }}
            />
          </g>
        ))}
      </svg>
    </div>
  );
}

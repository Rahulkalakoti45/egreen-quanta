import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, LoadingPane, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { axisTick, BAND_COLOR, SEVERITY_COLOR as SEV_COLOR, tooltipStyle } from "@/lib/chart";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { useCountUp } from "@/lib/motion";
import type { ThreatStats } from "@/types/api";

const TILE_META = [
  { key: "events", label: "Events", accent: "var(--primary)", icon: "M3 12h4l3 8 4-16 3 8h4" },
  { key: "invalid", label: "Invalid (24h)", accent: "var(--critical)", icon: "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" },
  { key: "alerts", label: "Open alerts", accent: "var(--high)", icon: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" },
  { key: "qvuln", label: "Quantum-vulnerable", accent: "var(--accent)", icon: "M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4Z" },
  { key: "mttt", label: "Mean time to triage", accent: "var(--ok)", icon: "M12 7v5l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" },
] as const;

export function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["threat-stats"],
    queryFn: () => api.get<ThreatStats>("/threats/stats"),
    refetchInterval: 15_000,
  });

  if (isLoading || !data) {
    return (
      <>
        <PageHeader eyebrow="Live" title="Security Operations Overview" />
        <LoadingPane />
      </>
    );
  }

  const mtttMin =
    data.mean_time_to_triage_seconds == null
      ? null
      : Math.round(data.mean_time_to_triage_seconds / 60);

  const donut = Object.entries(data.alerts_by_severity).map(([name, value]) => ({ name, value }));

  const tiles = [
    { meta: TILE_META[0], value: data.events_24h, hint: `${formatNumber(data.events_total)} total` },
    { meta: TILE_META[1], value: data.invalid_24h, hint: "failed verification" },
    { meta: TILE_META[2], value: data.open_alerts, hint: `${data.open_incidents} open incidents` },
    { meta: TILE_META[3], value: data.quantum_vulnerable_events, hint: "RSA/ECC · see Quantum Lab" },
    {
      meta: TILE_META[4],
      value: mtttMin,
      hint: "open → triaged",
      display: mtttMin == null ? "—" : `${mtttMin}m`,
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Live"
        title="Security Operations Overview"
        description="Digital-signature trust posture, live threats, and quantum-risk at a glance."
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {tiles.map((t, i) => (
          <Tile
            key={t.meta.key}
            meta={t.meta}
            value={t.value ?? 0}
            display={t.display}
            hint={t.hint}
            delay={i}
          />
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Card hover className="animate-fade-up lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-display text-sm font-semibold text-fg">
              Verification timeline · 7 days
            </h3>
            <Link to="/threats" className="text-xs text-primary hover:underline">
              alerts →
            </Link>
          </div>
          {data.timeline.length === 0 ? (
            <EmptyChart label="No events yet — verify a signature to populate." />
          ) : (
            <ResponsiveContainer width="100%" height={230}>
              <AreaChart data={data.timeline} margin={{ left: -18, right: 8, top: 8 }}>
                <defs>
                  {(["valid", "indeterminate", "invalid"] as const).map((k) => (
                    <linearGradient key={k} id={`t-${k}`} x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="0%"
                        stopColor={
                          k === "valid"
                            ? "rgb(var(--ok))"
                            : k === "invalid"
                              ? "rgb(var(--critical))"
                              : "rgb(var(--medium))"
                        }
                        stopOpacity={0.35}
                      />
                      <stop
                        offset="100%"
                        stopColor={
                          k === "valid"
                            ? "rgb(var(--ok))"
                            : k === "invalid"
                              ? "rgb(var(--critical))"
                              : "rgb(var(--medium))"
                        }
                        stopOpacity={0}
                      />
                    </linearGradient>
                  ))}
                </defs>
                <XAxis dataKey="date" tick={axisTick} stroke="rgb(var(--border))" />
                <YAxis tick={axisTick} allowDecimals={false} stroke="rgb(var(--border))" />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="valid" stackId="1" stroke="rgb(var(--ok))" strokeWidth={1.6} fill="url(#t-valid)" />
                <Area type="monotone" dataKey="indeterminate" stackId="1" stroke="rgb(var(--medium))" strokeWidth={1.6} fill="url(#t-indeterminate)" />
                <Area type="monotone" dataKey="invalid" stackId="1" stroke="rgb(var(--critical))" strokeWidth={1.6} fill="url(#t-invalid)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card hover className="animate-fade-up delay-1">
          <h3 className="mb-2 font-display text-sm font-semibold text-fg">Open alerts by severity</h3>
          {donut.length === 0 ? (
            <EmptyChart label="No open alerts" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={190}>
                <PieChart>
                  <Pie data={donut} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={3} stroke="none">
                    {donut.map((d) => (
                      <Cell key={d.name} fill={SEV_COLOR[d.name] ?? "rgb(var(--muted))"} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-1 flex flex-wrap gap-2 text-[11px]">
                {donut.map((d) => (
                  <span key={d.name} className="flex items-center gap-1.5 text-muted">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: SEV_COLOR[d.name] }} />
                    {d.name} <span className="font-mono text-fg">{d.value}</span>
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Card hover className="animate-fade-up">
          <h3 className="mb-3 font-display text-sm font-semibold text-fg">Top detections · 24h</h3>
          {data.top_rules.length === 0 ? (
            <p className="text-xs text-muted">No findings in the last 24 hours.</p>
          ) : (
            <ul className="space-y-2">
              {data.top_rules.map((r, i) => {
                const max = data.top_rules[0].count || 1;
                return (
                  <li key={r.code} className="flex items-center gap-2.5 text-xs">
                    <span className="w-10 font-mono text-muted">{r.code}</span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-hairline/10">
                      <span
                        className="block h-full rounded-full bg-brand-gradient animate-fade-in"
                        style={{ width: `${(r.count / max) * 100}%`, animationDelay: `${i * 60}ms` }}
                      />
                    </span>
                    <span className="w-6 text-right font-mono tabular-nums text-fg">{r.count}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card hover className="animate-fade-up delay-1">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-display text-sm font-semibold text-fg">Recent alerts</h3>
            <Link to="/threats" className="text-xs text-primary hover:underline">
              all →
            </Link>
          </div>
          {data.recent_alerts.length === 0 ? (
            <p className="text-xs text-muted">No alerts yet.</p>
          ) : (
            <ul className="space-y-1.5">
              {data.recent_alerts.map((a) => (
                <li key={a.id} className="flex items-center gap-2 rounded-lg px-1.5 py-1 text-xs transition-colors hover:bg-hairline/[0.04]">
                  <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: SEV_COLOR[a.severity] ?? "rgb(var(--muted))" }} />
                  <span className="flex-1 truncate text-fg" title={a.title}>
                    {a.title}
                  </span>
                  <span className="font-mono tabular-nums text-muted">{a.risk_score}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card hover className="animate-fade-up delay-2">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-display text-sm font-semibold text-fg">Post-quantum exposure</h3>
            <Link to="/quantum" className="text-xs text-primary hover:underline">
              lab →
            </Link>
          </div>
          {Object.keys(data.pqc_by_band).length === 0 ? (
            <p className="text-xs text-muted">Score the portfolio in the Quantum Lab to populate this.</p>
          ) : (
            <div className="space-y-2">
              {(["immediate", "plan", "monitor", "ok"] as const).map((band) => {
                const n = data.pqc_by_band[band] ?? 0;
                const total = Object.values(data.pqc_by_band).reduce((s, x) => s + x, 0) || 1;
                return (
                  <div key={band} className="flex items-center gap-2.5 text-xs">
                    <span className="w-16 capitalize text-muted">{band}</span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-hairline/10">
                      <span className="block h-full rounded-full" style={{ width: `${(n / total) * 100}%`, background: BAND_COLOR[band] }} />
                    </span>
                    <span className="w-6 text-right font-mono tabular-nums text-fg">{n}</span>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

function Tile({
  meta,
  value,
  display,
  hint,
  delay,
}: {
  meta: { label: string; accent: string; icon: string };
  value: number;
  display?: string;
  hint: string;
  delay: number;
}) {
  const shown = useCountUp(value, 900);
  return (
    <Card
      hover
      compact
      className={cn("group animate-fade-up overflow-hidden", `delay-${delay}`)}
    >
      <span
        className="pointer-events-none absolute -right-8 -top-8 h-20 w-20 rounded-full opacity-20 blur-2xl transition-opacity group-hover:opacity-40"
        style={{ background: `rgb(${meta.accent})` }}
      />
      <div className="relative flex items-start justify-between">
        <span className="text-[11px] uppercase tracking-wide text-muted">{meta.label}</span>
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke={`rgb(${meta.accent})`} strokeWidth={1.6} aria-hidden="true">
          <path d={meta.icon} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="relative mt-2 font-display text-3xl font-semibold tabular-nums text-fg">
        {display ?? formatNumber(Math.round(shown))}
      </div>
      <div className="relative mt-0.5 text-[11px] text-faint">{hint}</div>
    </Card>
  );
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="grid h-52 place-items-center rounded-xl border border-dashed border-hairline/12 text-xs text-muted">
      {label}
    </div>
  );
}

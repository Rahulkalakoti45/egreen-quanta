import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, Field, Input, Select } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { PortfolioItem, PortfolioResult, QESResult } from "@/types/api";

import { QesGauge } from "./lab/QesGauge";

function bandColor(qes: number): string {
  if (qes >= 75) return "rgb(var(--critical))";
  if (qes >= 50) return "rgb(var(--medium))";
  if (qes >= 25) return "rgb(var(--low))";
  return "rgb(var(--ok))";
}

export function QuantumRiskPanel() {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)]">
      <ScoreForm />
      <Portfolio />
    </div>
  );
}

function ScoreForm() {
  const [algo, setAlgo] = useState("rsa");
  const [keyBits, setKeyBits] = useState("2048");
  const [curve, setCurve] = useState("secp256r1");
  const [life, setLife] = useState("7");
  const [exposure, setExposure] = useState("transmitted");

  const score = useMutation<QESResult, ApiError>({
    mutationFn: () =>
      api.post<QESResult>("/quantum/pq-risk/score", {
        algo,
        key_bits: algo === "rsa" ? Number(keyBits) : null,
        curve: algo === "ec" ? curve : null,
        data_lifetime_years: Number(life),
        exposure,
      }),
  });

  const isEc = algo === "ec";
  const r = score.data;

  const factors: [string, number][] = r
    ? [
        ["algorithm", r.algo_factor],
        ["strength", r.strength_factor],
        ["longevity", r.longevity_factor],
        ["exposure", r.exposure_factor],
      ]
    : [];

  return (
    <Card className="space-y-4">
      <div>
        <h3 className="font-display text-sm font-semibold text-fg">Score a signing key</h3>
        <p className="mt-0.5 text-xs text-muted">
          Shor / Grover exposure &amp; harvest-now-decrypt-later risk for one identity.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Algorithm" htmlFor="q-algo">
          <Select id="q-algo" value={algo} onChange={(e) => setAlgo(e.target.value)}>
            <option value="rsa">RSA</option>
            <option value="ec">ECDSA / ECDH</option>
            <option value="ed25519">Ed25519</option>
            <option value="ml-dsa">ML-DSA (Dilithium)</option>
            <option value="slh-dsa">SLH-DSA (SPHINCS+)</option>
          </Select>
        </Field>
        {algo === "rsa" && (
          <Field label="Key size (bits)" htmlFor="q-bits">
            <Select id="q-bits" value={keyBits} onChange={(e) => setKeyBits(e.target.value)}>
              {["1024", "2048", "3072", "4096", "7680", "15360"].map((b) => (
                <option key={b}>{b}</option>
              ))}
            </Select>
          </Field>
        )}
        {isEc && (
          <Field label="Curve" htmlFor="q-curve">
            <Select id="q-curve" value={curve} onChange={(e) => setCurve(e.target.value)}>
              <option value="secp256r1">P-256</option>
              <option value="secp384r1">P-384</option>
              <option value="secp521r1">P-521</option>
            </Select>
          </Field>
        )}
        <Field label="Trustworthy for (years)" htmlFor="q-life">
          <Input
            id="q-life"
            type="number"
            min={0}
            max={50}
            value={life}
            onChange={(e) => setLife(e.target.value)}
          />
        </Field>
        <Field label="Exposure" htmlFor="q-exp">
          <Select id="q-exp" value={exposure} onChange={(e) => setExposure(e.target.value)}>
            <option value="public">Public (published)</option>
            <option value="transmitted">Transmitted over network</option>
            <option value="internal">Internal only</option>
            <option value="sealed">Sealed / air-gapped</option>
          </Select>
        </Field>
      </div>

      <Button
        size="lg"
        className="w-full"
        onClick={() => score.mutate()}
        loading={score.isPending}
      >
        {score.isPending ? "Scoring" : "Compute Quantum Exposure Score"}
      </Button>

      {r && (
        <div className="animate-fade-up rounded-xl border border-hairline/10 bg-hairline/[0.02] p-4">
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-5">
            <QesGauge value={r.qes} band={r.band} />
            <div className="w-full min-w-0 flex-1 space-y-2.5">
              {factors.map(([k, v], i) => (
                <div key={k} className="text-[11px]">
                  <div className="mb-1 flex items-center justify-between gap-3">
                    <span className="uppercase tracking-wide text-muted">{k}</span>
                    <span className="font-mono tabular-nums text-fg">{v.toFixed(2)}</span>
                  </div>
                  <span className="block h-1.5 overflow-hidden rounded-full bg-hairline/10">
                    <span
                      className="block h-full rounded-full animate-fade-in"
                      style={{
                        width: `${Math.min(100, v * 100)}%`,
                        background: bandColor(r.qes),
                        animationDelay: `${i * 80}ms`,
                      }}
                    />
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/[0.06] p-2.5">
            <svg viewBox="0 0 24 24" className="mt-0.5 h-4 w-4 shrink-0 text-primary" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
              <path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4Z" strokeLinejoin="round" />
              <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="text-xs leading-relaxed text-fg">{r.recommendation}</p>
          </div>
        </div>
      )}
      {score.error && <p className="text-xs text-critical">{score.error.message}</p>}
    </Card>
  );
}

function Portfolio() {
  const [life, setLife] = useState("7");
  const run = useMutation<PortfolioResult, ApiError>({
    mutationFn: () =>
      api.post<PortfolioResult>("/quantum/pq-risk/portfolio", {
        lookback_days: 30,
        data_lifetime_years: Number(life),
        exposure: "public",
      }),
  });
  const d = run.data;

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="font-display text-sm font-semibold text-fg">Portfolio quantum-risk heatmap</h3>
          <p className="mt-0.5 text-xs text-muted">
            Every signing identity seen in 30 days, scored for HNDL exposure.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            value={life}
            min={0}
            max={50}
            onChange={(e) => setLife(e.target.value)}
            className="h-9 w-16"
            aria-label="Data lifetime years"
          />
          <Button size="md" onClick={() => run.mutate()} loading={run.isPending}>
            {run.isPending ? "Scoring" : "Score portfolio"}
          </Button>
        </div>
      </div>

      {d ? (
        d.items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-hairline/12 py-8 text-center text-sm text-muted">
            No signing identities observed yet — run some verifications first.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-lg border border-hairline/10 bg-hairline/[0.03] px-2 py-1">
                {d.scored} identities
              </span>
              <span className="rounded-lg border border-hairline/10 bg-hairline/[0.03] px-2 py-1">
                mean QES <span className="font-mono font-semibold text-fg">{d.mean_qes}</span>
              </span>
              {Object.entries(d.by_band).map(([b, n]) => (
                <span
                  key={b}
                  className="rounded-lg border px-2 py-1 font-medium"
                  style={{
                    borderColor: `${bandColor(b === "immediate" ? 90 : b === "plan" ? 60 : b === "monitor" ? 30 : 10)}40`,
                    color: bandColor(b === "immediate" ? 90 : b === "plan" ? 60 : b === "monitor" ? 30 : 10),
                  }}
                >
                  {n} {b}
                </span>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {d.items.map((it: PortfolioItem, i) => {
                const c = bandColor(it.qes);
                return (
                  <div
                    key={it.spki_sha256 ?? i}
                    className="group relative animate-fade-up overflow-hidden rounded-xl border p-2.5"
                    style={{
                      background: `linear-gradient(160deg, ${c}1f, transparent)`,
                      borderColor: `${c}44`,
                      animationDelay: `${Math.min(i * 40, 400)}ms`,
                    }}
                  >
                    <span
                      className="absolute -right-6 -top-6 h-16 w-16 rounded-full opacity-30 blur-xl"
                      style={{ background: c }}
                    />
                    <div className="relative flex items-center justify-between">
                      <span
                        className="font-display text-lg font-semibold tabular-nums"
                        style={{ color: c }}
                      >
                        {it.qes}
                      </span>
                      <span className="text-[10px] text-muted">{it.event_count}×</span>
                    </div>
                    <div className="relative mt-0.5 truncate text-xs font-medium text-fg" title={it.label}>
                      {it.label}
                    </div>
                    <div className="relative font-mono text-[10px] text-muted">
                      {it.algo}
                      {it.key_bits ? `-${it.key_bits}` : ""} {it.curve ?? ""}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )
      ) : (
        <div className="grid place-items-center rounded-xl border border-dashed border-hairline/12 py-14 text-center">
          <div className="mb-2 h-9 w-9 rounded-xl bg-primary/10 blur-[1px]" />
          <p className="text-sm text-muted">Run to populate the heatmap.</p>
        </div>
      )}
      {run.error && <p className="text-xs text-critical">{run.error.message}</p>}
    </Card>
  );
}

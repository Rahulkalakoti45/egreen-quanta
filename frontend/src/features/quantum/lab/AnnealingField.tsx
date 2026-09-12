import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import type { SolverInfo } from "@/types/api";

/* ---- deterministic RNG so a given seed always paints the same lattice ---- */
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Node {
  x: number;
  y: number;
  state: number; // -1 | +1
  freezeAt: number; // 0..1 progress point where this spin locks in
  critical: boolean;
}

/**
 * Illustrative simulated-annealing field. The spin lattice dynamics are a
 * client-side illustration; the energy trace and metrics shown are the real
 * solver output passed in `solver`.
 */
export function AnnealingField({
  solver,
  className,
}: {
  solver?: SolverInfo;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>();
  const startRef = useRef<number>(0);
  const [replayKey, setReplayKey] = useState(0);
  const [hud, setHud] = useState({ temp: 1, energy: 0, frozen: 0, iter: 0 });

  const seed = solver?.seed ?? 1337;
  const sweeps = solver?.sweeps ?? 2000;
  const traj = useMemo(
    () => solver?.energy_trajectory ?? [],
    [solver?.energy_trajectory],
  );
  const bestEnergy = solver?.best_energy ?? 0;

  // Build the lattice once per seed / size.
  const nodes = useMemo<Node[]>(() => {
    const rnd = mulberry32(seed);
    const cols = 22;
    const rows = 12;
    const out: Node[] = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const jitterX = (rnd() - 0.5) * 0.5;
        const jitterY = (rnd() - 0.5) * 0.5;
        out.push({
          x: (c + 0.5 + jitterX) / cols,
          y: (r + 0.5 + jitterY) / rows,
          state: rnd() > 0.5 ? 1 : -1,
          freezeAt: 0.15 + rnd() * 0.8,
          critical: rnd() > 0.93,
        });
      }
    }
    return out;
  }, [seed]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const DURATION = reduced ? 1 : 2600;
    let w = 0;
    let h = 0;
    const dpr = Math.min(2, window.devicePixelRatio || 1);

    const resize = () => {
      w = wrap.clientWidth;
      h = wrap.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    startRef.current = performance.now();
    const rnd = mulberry32(seed ^ 0x9e3779b9);
    // per-node phase for idle shimmer
    const phase = nodes.map(() => rnd() * Math.PI * 2);

    const cyan = "56, 211, 238";
    const violet = "167, 139, 250";

    const frame = (now: number) => {
      const elapsed = now - startRef.current;
      const p = Math.min(1, elapsed / DURATION); // anneal progress 0..1
      const ease = 1 - Math.pow(1 - p, 2.2);
      const temperature = Math.max(0.02, 1 - ease); // cools to ~0

      ctx.clearRect(0, 0, w, h);

      // faint bounding frame
      ctx.strokeStyle = "rgba(148,163,210,0.08)";
      ctx.lineWidth = 1;
      ctx.strokeRect(6, 6, w - 12, h - 12);

      let frozenCount = 0;
      const px = (n: Node) => 14 + n.x * (w - 28);
      const py = (n: Node) => 14 + n.y * (h - 28);

      // links between near neighbours (cheap: only right + down in grid order)
      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        for (const j of [i + 1, i + 22]) {
          const m = nodes[j];
          if (!m) continue;
          const dx = px(n) - px(m);
          const dy = py(n) - py(m);
          if (Math.abs(dx) > w / 10 || Math.abs(dy) > h / 6) continue;
          const aligned = n.state === m.state;
          ctx.strokeStyle = aligned
            ? `rgba(${cyan}, ${0.05 + (1 - temperature) * 0.08})`
            : `rgba(${violet}, ${0.04 + temperature * 0.06})`;
          ctx.beginPath();
          ctx.moveTo(px(n), py(n));
          ctx.lineTo(px(m), py(m));
          ctx.stroke();
        }
      }

      // nodes
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        const frozen = p >= n.freezeAt;
        if (frozen) {
          frozenCount++;
        } else if (Math.random() < temperature * 0.12) {
          // still "hot" — flip
          n.state = Math.random() > 0.5 ? 1 : -1;
        }
        const x = px(n);
        const y = py(n);
        const shimmer = frozen ? 0 : Math.sin(now / 220 + phase[i]) * 1.1 * temperature;
        const base = n.state > 0 ? cyan : violet;
        const settleGlow = frozen ? 0.9 : 0.35 + temperature * 0.3;
        const rad = (n.critical ? 3.1 : 2.1) + (frozen && n.critical ? Math.sin(now / 300) * 0.7 : 0);

        if (frozen && n.critical) {
          ctx.beginPath();
          ctx.arc(x, y, rad + 5, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${base}, 0.12)`;
          ctx.fill();
        }
        ctx.beginPath();
        ctx.arc(x + shimmer, y + shimmer, rad, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${base}, ${settleGlow})`;
        ctx.shadowColor = `rgba(${base}, ${frozen ? 0.8 : 0.3})`;
        ctx.shadowBlur = frozen ? (n.critical ? 12 : 6) : 3;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      const frozenFrac = frozenCount / nodes.length;
      const tIdx = Math.min(traj.length - 1, Math.floor(p * (traj.length - 1)));
      const energy = traj.length ? traj[Math.max(0, tIdx)] : bestEnergy;
      setHud({
        temp: temperature,
        energy,
        frozen: frozenFrac,
        iter: Math.floor(p * sweeps),
      });

      if (p < 1 && !reduced) {
        rafRef.current = requestAnimationFrame(frame);
      } else {
        // settle frame
        rafRef.current = requestAnimationFrame(function settle(n2) {
          drawSettled(n2);
        });
      }
    };

    const drawSettled = (now: number) => {
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = "rgba(148,163,210,0.08)";
      ctx.strokeRect(6, 6, w - 12, h - 12);
      const px = (n: Node) => 14 + n.x * (w - 28);
      const py = (n: Node) => 14 + n.y * (h - 28);
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        for (const j of [i + 1, i + 22]) {
          const m = nodes[j];
          if (!m) continue;
          if (Math.abs(px(n) - px(m)) > w / 10 || Math.abs(py(n) - py(m)) > h / 6) continue;
          ctx.strokeStyle =
            n.state === m.state ? "rgba(56,211,238,0.12)" : "rgba(167,139,250,0.06)";
          ctx.beginPath();
          ctx.moveTo(px(n), py(n));
          ctx.lineTo(px(m), py(m));
          ctx.stroke();
        }
      }
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        const base = n.state > 0 ? "56, 211, 238" : "167, 139, 250";
        const x = px(n);
        const y = py(n);
        const pulse = n.critical ? Math.sin(now / 320 + i) * 0.6 : 0;
        if (n.critical) {
          ctx.beginPath();
          ctx.arc(x, y, 8 + pulse, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${base}, 0.12)`;
          ctx.fill();
        }
        ctx.beginPath();
        ctx.arc(x, y, (n.critical ? 3.2 : 2.1) + pulse * 0.4, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${base}, 0.92)`;
        ctx.shadowColor = `rgba(${base}, 0.8)`;
        ctx.shadowBlur = n.critical ? 12 : 5;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
      rafRef.current = requestAnimationFrame(drawSettled);
    };

    rafRef.current = requestAnimationFrame(frame);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, [nodes, seed, sweeps, traj, bestEnergy, replayKey]);

  const tempPct = Math.round(hud.temp * 100);
  const frozenPct = Math.round(hud.frozen * 100);

  return (
    <div className={cn("relative", className)}>
      <div
        ref={wrapRef}
        className="relative h-56 w-full overflow-hidden rounded-xl border border-hairline/10 bg-[radial-gradient(ellipse_at_50%_0%,rgb(var(--primary)/0.08),transparent_70%)]"
      >
        <canvas ref={canvasRef} className="absolute inset-0" />

        {/* HUD */}
        <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3">
          <div className="flex items-start justify-between">
            <div className="rounded-lg border border-hairline/10 bg-bg/60 px-2.5 py-1.5 backdrop-blur">
              <div className="text-[9px] uppercase tracking-wider text-faint">energy</div>
              <div className="font-mono text-sm font-semibold text-primary tabular-nums">
                {hud.energy.toFixed(2)}
              </div>
            </div>
            <div className="rounded-lg border border-hairline/10 bg-bg/60 px-2.5 py-1.5 text-right backdrop-blur">
              <div className="text-[9px] uppercase tracking-wider text-faint">sweep</div>
              <div className="font-mono text-sm font-semibold text-fg tabular-nums">
                {hud.iter.toLocaleString()}
              </div>
            </div>
          </div>

          <div className="flex items-end justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[9px] uppercase tracking-wider text-faint">T</span>
              <span className="relative block h-1.5 w-24 overflow-hidden rounded-full bg-hairline/10">
                <span
                  className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-accent-2 via-high to-primary transition-[width] duration-200"
                  style={{ width: `${Math.max(3, tempPct)}%` }}
                />
              </span>
              <span className="font-mono text-[10px] text-muted tabular-nums">{tempPct}%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-muted tabular-nums">
                {frozenPct}% settled
              </span>
              <span className="relative block h-1.5 w-24 overflow-hidden rounded-full bg-hairline/10">
                <span
                  className="absolute inset-y-0 left-0 rounded-full bg-primary transition-[width] duration-200"
                  style={{ width: `${frozenPct}%` }}
                />
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <p className="text-[10.5px] leading-tight text-faint">
          Illustrative spin-lattice dynamics · energy trace &amp; metrics are real solver output
        </p>
        <button
          onClick={() => {
            startRef.current = performance.now();
            setReplayKey((k) => k + 1);
          }}
          className="inline-flex items-center gap-1.5 rounded-lg border border-hairline/10 bg-hairline/[0.04] px-2.5 py-1 text-[11px] font-medium text-muted transition-colors hover:border-hairline/20 hover:text-fg"
        >
          <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
            <path d="M3 12a9 9 0 1 0 3-6.7M3 4v4h4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Replay
        </button>
      </div>
    </div>
  );
}

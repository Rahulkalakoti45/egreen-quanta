import { useCountUp } from "@/lib/motion";

const BANDS = [
  { at: 0, color: "var(--ok)" },
  { at: 25, color: "var(--low)" },
  { at: 50, color: "var(--medium)" },
  { at: 75, color: "var(--critical)" },
];

function colorFor(v: number): string {
  const b = [...BANDS].reverse().find((x) => v >= x.at) ?? BANDS[0];
  return `rgb(${b.color})`;
}

/** Radial 240° gauge for a 0–100 Quantum Exposure Score. */
export function QesGauge({
  value,
  band,
  size = 168,
}: {
  value: number;
  band: string;
  size?: number;
}) {
  const shown = useCountUp(value, 1100);
  const stroke = 12;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const START = 150; // degrees
  const SWEEP = 240;
  const circ = 2 * Math.PI * r;
  const arcLen = (SWEEP / 360) * circ;
  const progress = Math.min(100, Math.max(0, shown)) / 100;
  const color = colorFor(shown);

  const polar = (deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)] as const;
  };
  const [sx, sy] = polar(START);
  const [ex, ey] = polar(START + SWEEP);
  const largeArc = SWEEP > 180 ? 1 : 0;

  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-0">
        <defs>
          <linearGradient id="qesArc" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.6} />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
          <filter id="qesGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {/* track */}
        <path
          d={`M ${sx} ${sy} A ${r} ${r} 0 ${largeArc} 1 ${ex} ${ey}`}
          fill="none"
          stroke="rgb(var(--hairline) / 0.08)"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        {/* value arc */}
        <path
          d={`M ${sx} ${sy} A ${r} ${r} 0 ${largeArc} 1 ${ex} ${ey}`}
          fill="none"
          stroke="url(#qesArc)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${arcLen} ${circ}`}
          strokeDashoffset={arcLen * (1 - progress)}
          filter="url(#qesGlow)"
          style={{ transition: "stroke-dashoffset 0.2s linear" }}
        />
        {/* tick marks */}
        {[0, 25, 50, 75, 100].map((t) => {
          const [tx, ty] = polar(START + (t / 100) * SWEEP);
          const [tx2, ty2] = (() => {
            const rad = ((START + (t / 100) * SWEEP) * Math.PI) / 180;
            const rr = r + stroke / 2 + 3;
            return [cx + rr * Math.cos(rad), cy + rr * Math.sin(rad)] as const;
          })();
          return (
            <line
              key={t}
              x1={tx}
              y1={ty}
              x2={tx2}
              y2={ty2}
              stroke="rgb(var(--faint) / 0.5)"
              strokeWidth={1}
            />
          );
        })}
      </svg>
      <div className="absolute flex flex-col items-center">
        <span
          className="font-display text-4xl font-semibold tabular-nums"
          style={{ color, textShadow: `0 0 24px ${color}55` }}
        >
          {Math.round(shown)}
        </span>
        <span
          className="mt-0.5 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
          style={{ background: `${color}22`, color }}
        >
          {band}
        </span>
      </div>
    </div>
  );
}

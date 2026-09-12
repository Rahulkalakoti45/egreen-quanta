/** Shared Recharts styling that follows the theme tokens. */

export const tooltipStyle: React.CSSProperties = {
  background: "rgb(var(--surface) / 0.85)",
  border: "1px solid rgb(var(--hairline) / 0.12)",
  borderRadius: 10,
  fontSize: 12,
  color: "rgb(var(--fg))",
  backdropFilter: "blur(8px)",
  boxShadow: "0 8px 30px -12px rgb(0 0 0 / 0.6)",
};

export const axisTick = { fontSize: 11, fill: "rgb(var(--muted))" };

export const SEVERITY_COLOR: Record<string, string> = {
  critical: "rgb(var(--critical))",
  high: "rgb(var(--high))",
  medium: "rgb(var(--medium))",
  low: "rgb(var(--low))",
  info: "rgb(var(--info))",
  ok: "rgb(var(--ok))",
};

export const BAND_COLOR: Record<string, string> = {
  immediate: "rgb(var(--critical))",
  plan: "rgb(var(--medium))",
  monitor: "rgb(var(--low))",
  ok: "rgb(var(--ok))",
};

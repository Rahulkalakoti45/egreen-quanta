import type { Config } from "tailwindcss";

/**
 * "Quantum SOC" palette. Semantic tokens map to CSS variables defined in
 * src/styles/index.css so the whole app themes from one place.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)",
        "bg-2": "rgb(var(--bg-2) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        "surface-2": "rgb(var(--surface-2) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        "border-strong": "rgb(var(--border-strong) / <alpha-value>)",
        hairline: "rgb(var(--hairline) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        faint: "rgb(var(--faint) / <alpha-value>)",
        fg: "rgb(var(--fg) / <alpha-value>)",
        primary: "rgb(var(--primary) / <alpha-value>)",
        "primary-2": "rgb(var(--primary-2) / <alpha-value>)",
        "primary-fg": "rgb(var(--primary-fg) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        "accent-2": "rgb(var(--accent-2) / <alpha-value>)",
        critical: "rgb(var(--critical) / <alpha-value>)",
        high: "rgb(var(--high) / <alpha-value>)",
        medium: "rgb(var(--medium) / <alpha-value>)",
        low: "rgb(var(--low) / <alpha-value>)",
        info: "rgb(var(--info) / <alpha-value>)",
        ok: "rgb(var(--ok) / <alpha-value>)",
        glow: "rgb(var(--glow) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.30), 0 8px 30px -12px rgb(0 0 0 / 0.45)",
        glow: "0 0 24px -6px rgb(var(--glow) / 0.5)",
        "glow-lg": "0 0 60px -12px rgb(var(--glow) / 0.55)",
        "glow-sm": "0 0 12px -2px rgb(var(--glow) / 0.55)",
        "inner-top": "inset 0 1px 0 0 rgb(var(--hairline) / 0.08)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(110deg, rgb(var(--primary)), rgb(var(--primary-2)))",
        "radial-fade": "radial-gradient(ellipse at top, rgb(var(--primary) / 0.12), transparent 60%)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "none" },
        },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.96)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "100% 0" },
          "100%": { backgroundPosition: "-100% 0" },
        },
        "pulse-glow": {
          "0%,100%": { opacity: "1", boxShadow: "0 0 0 0 rgb(var(--glow) / 0.5)" },
          "50%": { opacity: "0.85", boxShadow: "0 0 0 6px rgb(var(--glow) / 0)" },
        },
        "spin-slow": { to: { transform: "rotate(360deg)" } },
        "float-y": {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s cubic-bezier(0.22,1,0.36,1) both",
        "fade-in": "fade-in 0.4s ease both",
        "scale-in": "scale-in 0.4s cubic-bezier(0.22,1,0.36,1) both",
        shimmer: "shimmer 1.4s ease-in-out infinite",
        "pulse-glow": "pulse-glow 2.4s ease-in-out infinite",
        "spin-slow": "spin-slow 14s linear infinite",
        float: "float-y 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;

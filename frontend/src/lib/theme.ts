import { useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

const KEY = "egq.theme";

function read(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* ignore */
  }
  // Dark-first product: default to the SOC dark theme until the user chooses.
  return "dark";
}

function systemDark(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? true;
}

function apply(theme: Theme): void {
  const el = document.documentElement;
  const dark = theme === "dark" || (theme === "system" && systemDark());
  el.classList.toggle("dark", dark);
  el.classList.toggle("light", !dark);
  el.style.colorScheme = dark ? "dark" : "light";
}

/** Applied once at module load so there's no flash before React mounts. */
apply(read());

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(read);

  useEffect(() => {
    apply(theme);
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => apply("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = (t: Theme) => {
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* ignore */
    }
    setThemeState(t);
  };

  return [theme, setTheme];
}

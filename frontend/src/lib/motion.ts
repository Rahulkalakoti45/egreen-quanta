import { useEffect, useRef, useState } from "react";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * Animate a number from 0 (or its previous value) to `target`. Returns the
 * current display value. Honours prefers-reduced-motion by snapping.
 */
export function useCountUp(target: number, durationMs = 900, decimals = 0): number {
  const [value, setValue] = useState(0);
  const fromRef = useRef(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    if (prefersReducedMotion()) {
      setValue(target);
      return;
    }
    const from = fromRef.current;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const v = from + (target - from) * easeOutCubic(t);
      setValue(v);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      fromRef.current = value;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs]);

  const p = Math.pow(10, decimals);
  return Math.round(value * p) / p;
}

/**
 * Step an index from 0 → length-1 over `durationMs`, for replaying a recorded
 * trajectory (e.g. a solver's energy history). Returns [index, playing, replay].
 */
export function useTrajectoryPlayer(
  length: number,
  durationMs = 1600,
): [number, boolean, () => void] {
  const [idx, setIdx] = useState(Math.max(0, length - 1));
  const [playing, setPlaying] = useState(false);
  const rafRef = useRef<number>();
  const tokenRef = useRef(0);

  const run = () => {
    if (length <= 1) return;
    if (prefersReducedMotion()) {
      setIdx(length - 1);
      return;
    }
    const token = ++tokenRef.current;
    setPlaying(true);
    const start = performance.now();
    const tick = (now: number) => {
      if (token !== tokenRef.current) return;
      const t = Math.min(1, (now - start) / durationMs);
      setIdx(Math.round(t * (length - 1)));
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setPlaying(false);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  // auto-play whenever a new trajectory arrives
  useEffect(() => {
    run();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [length]);

  return [idx, playing, run];
}

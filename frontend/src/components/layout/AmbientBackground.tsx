/**
 * Fixed, non-interactive backdrop: three slow-drifting colour blobs plus a
 * radially-masked engineering grid. Pure CSS — cheap, and disabled under
 * prefers-reduced-motion by the utility classes themselves.
 */
export function AmbientBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-bg" />
      {/* colour mesh */}
      <div className="absolute -left-[15%] -top-[20%] h-[55vmax] w-[55vmax] animate-aurora-1 rounded-full bg-primary/20 blur-[120px]" />
      <div className="absolute -right-[15%] top-[5%] h-[50vmax] w-[50vmax] animate-aurora-2 rounded-full bg-accent/18 blur-[120px]" />
      <div className="absolute bottom-[-25%] left-[20%] h-[45vmax] w-[45vmax] animate-aurora-3 rounded-full bg-accent-2/12 blur-[130px]" />
      {/* engineering grid */}
      <div className="absolute inset-0 grid-bg opacity-70" />
      {/* vignette to seat content */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_35%,rgb(var(--bg)/0.85)_100%)]" />
    </div>
  );
}

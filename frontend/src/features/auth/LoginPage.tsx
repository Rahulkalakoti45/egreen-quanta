import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  { role: "admin", email: "admin@egreen.local" },
  { role: "analyst", email: "analyst@egreen.local" },
  { role: "auditor", email: "auditor@egreen.local" },
  { role: "viewer", email: "viewer@egreen.local" },
];
const DEMO_PASSWORD = "EgreenQuanta!2026";

export function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: string } };

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") {
    return <Navigate to={location.state?.from ?? "/"} replace />;
  }

  async function submit(e: FormEvent, creds?: { email: string; password: string }) {
    e.preventDefault();
    const em = creds?.email ?? email;
    const pw = creds?.password ?? password;
    setBusy(true);
    setError(null);
    try {
      await login(em, pw, needsTotp ? totp : undefined);
      navigate(location.state?.from ?? "/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.code === "mfa_required") {
        setNeedsTotp(true);
        setError("Enter the 6-digit code from your authenticator app.");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to sign in. Check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* ambient backdrop */}
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-bg">
        <div className="absolute -left-[10%] top-[-10%] h-[60vmax] w-[60vmax] animate-aurora-1 rounded-full bg-primary/20 blur-[130px]" />
        <div className="absolute -right-[10%] bottom-[-10%] h-[55vmax] w-[55vmax] animate-aurora-2 rounded-full bg-accent/16 blur-[130px]" />
        <div className="absolute inset-0 grid-bg opacity-60" />
      </div>

      {/* brand / story panel */}
      <div className="relative hidden flex-col justify-between p-12 lg:flex">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-gradient text-primary-fg shadow-glow">
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6" aria-hidden="true">
              <path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4Z" stroke="currentColor" strokeWidth={1.7} />
              <circle cx="12" cy="11" r="2.5" stroke="currentColor" strokeWidth={1.7} />
            </svg>
          </div>
          <div>
            <div className="font-display text-lg font-semibold text-fg">Egreen Quanta</div>
            <div className="text-[10px] font-medium uppercase tracking-[0.24em] text-muted">
              Quantum SOC
            </div>
          </div>
        </div>

        <div className="max-w-md">
          <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight text-fg">
            Digital-signature trust,
            <span className="text-gradient"> quantum-ready</span>.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-muted">
            Verify RSA / ECC / EdDSA signatures and X.509 chains, detect signature-security threats
            with a rule engine plus local ML, and score every key for quantum exposure — with a
            tamper-evident audit trail.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {["PAdES · CMS · JWS", "19 detection rules", "SA / SQA over QUBO", "Hash-chained audit"].map(
              (t) => (
                <span
                  key={t}
                  className="rounded-full border border-hairline/10 bg-hairline/[0.03] px-3 py-1 text-[11px] text-muted"
                >
                  {t}
                </span>
              ),
            )}
          </div>
        </div>

        <p className="text-[11px] text-faint">Problem Statement 141 · SIH 2026 · Blockchain &amp; Cybersecurity</p>
      </div>

      {/* auth card */}
      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm animate-fade-up">
          <div className="mb-6 flex items-center gap-2.5 lg:hidden">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-gradient text-primary-fg shadow-glow-sm">
              <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6" aria-hidden="true">
                <path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4Z" stroke="currentColor" strokeWidth={1.6} />
                <circle cx="12" cy="11" r="2.5" stroke="currentColor" strokeWidth={1.6} />
              </svg>
            </div>
            <div>
              <div className="font-display text-base font-semibold text-fg">Egreen Quanta</div>
              <div className="text-[10px] uppercase tracking-[0.22em] text-muted">Quantum SOC</div>
            </div>
          </div>

          <div className="glass-strong rounded-2xl p-6">
            <h2 className="font-display text-lg font-semibold text-fg">Sign in</h2>
            <p className="mt-1 text-xs text-muted">Use a demo account below, or your credentials.</p>

            <form onSubmit={(e) => submit(e)} className="mt-5 space-y-4">
              <div>
                <label htmlFor="email" className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-muted">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-hairline/10 bg-hairline/[0.03] px-3 py-2 text-sm text-fg outline-none transition-all placeholder:text-faint focus:border-primary/50 focus:ring-4 focus:ring-primary/10"
                />
              </div>
              <div>
                <label htmlFor="password" className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-muted">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-hairline/10 bg-hairline/[0.03] px-3 py-2 text-sm text-fg outline-none transition-all placeholder:text-faint focus:border-primary/50 focus:ring-4 focus:ring-primary/10"
                />
              </div>
              {needsTotp && (
                <div>
                  <label htmlFor="totp" className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-muted">
                    Authenticator code
                  </label>
                  <input
                    id="totp"
                    inputMode="numeric"
                    pattern="\d{6}"
                    maxLength={6}
                    autoComplete="one-time-code"
                    value={totp}
                    onChange={(e) => setTotp(e.target.value.replace(/\D/g, ""))}
                    className="w-full rounded-lg border border-hairline/10 bg-hairline/[0.03] px-3 py-2 font-mono text-sm tracking-[0.4em] text-fg outline-none focus:border-primary/50 focus:ring-4 focus:ring-primary/10"
                  />
                </div>
              )}

              {error && (
                <p
                  className={
                    needsTotp && error.startsWith("Enter")
                      ? "text-xs text-muted"
                      : "text-xs text-critical"
                  }
                >
                  {error}
                </p>
              )}

              <Button type="submit" size="lg" className="w-full" loading={busy}>
                {busy ? "Signing in" : "Sign in"}
              </Button>
            </form>
          </div>

          <div className="mt-4 rounded-xl border border-hairline/10 bg-hairline/[0.02] p-3">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-faint">
              Demo accounts · one click
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {DEMO_ACCOUNTS.map((a) => (
                <button
                  key={a.role}
                  disabled={busy}
                  onClick={(e) => {
                    setEmail(a.email);
                    setPassword(DEMO_PASSWORD);
                    void submit(e, { email: a.email, password: DEMO_PASSWORD });
                  }}
                  className="group flex items-center justify-between rounded-lg border border-hairline/10 bg-hairline/[0.03] px-2.5 py-1.5 text-left text-xs transition-colors hover:border-primary/40 hover:bg-primary/[0.06] disabled:opacity-50"
                >
                  <span className="font-medium capitalize text-fg">{a.role}</span>
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 text-faint transition-colors group-hover:text-primary" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                    <path d="M5 12h14m-6-6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

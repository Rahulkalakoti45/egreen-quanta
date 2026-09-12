# Egreen Quanta — System Architecture

**Quantum-Inspired Cyber Threat Detection for Digital Signature Security**
SIH 2026 · Problem Statement 141 · Theme: Blockchain & Cybersecurity

---

## Table of contents

1. [Product overview](#1-product-overview)
2. [Threat model](#2-threat-model)
3. [High-level architecture](#3-high-level-architecture)
4. [Module breakdown](#4-module-breakdown)
5. [Data model](#5-data-model)
6. [Security architecture](#6-security-architecture)
7. [Quantum-inspired subsystem](#7-quantum-inspired-subsystem)
8. [ML anomaly detection](#8-ml-anomaly-detection)
9. [Technology stack & rationale](#9-technology-stack--rationale)
10. [Repository structure](#10-repository-structure)
11. [API surface](#11-api-surface)
12. [Deployment](#12-deployment)
13. [Observability & testing](#13-observability--testing)
14. [Build sequence](#14-build-sequence)
15. [Requirement traceability](#15-requirement-traceability)

---

## 1. Product overview

Egreen Quanta is a **Security Operations Center (SOC) platform specialised for digital-signature
and PKI trust**. It ingests signature-verification and certificate-validation events (submitted
via API, uploaded documents, or connectors), runs a deterministic **cryptographic verification
core**, layers a **rule-based + ML threat-detection engine** on top, and uses a
**quantum-inspired optimisation subsystem** for three jobs:

| Job | What it does |
|---|---|
| **Quantum-risk scoring** (hero) | Scores every signature/certificate for exposure to a cryptographically-relevant quantum computer (Shor/Grover) and "harvest-now, decrypt-later" risk; produces a post-quantum (PQC) migration plan. |
| **Detection tuning** | Simulated (quantum) annealing over a QUBO to tune rule weights and anomaly thresholds against labelled history, maximising F1. |
| **Threat correlation** | Groups scattered events into incidents by solving a max-weight-clique / community QUBO on the event-similarity graph. |

Operators work in a **modern dark SOC dashboard**: KPI tiles, live alert feed, incident kanban,
signature/certificate explorer with full cryptographic findings, a "Quantum Lab" for running and
visualising optimisations, a tamper-evident audit-log viewer, and admin screens for users,
rules, and the CA trust store.

### Design principles

- **Local-first / no external dependency for core function.** Crypto, detection, quantum-inspired
  optimisation and ML all run on-box. No third-party API calls in the request path. Network egress
  (OCSP/CRL/TSA) is opt-in, timeout-bounded and SSRF-guarded.
- **Deterministic core, probabilistic edge.** Cryptographic verdicts are exact and reproducible.
  ML and quantum-inspired heuristics *advise* — they never override a hard cryptographic failure.
- **Tamper-evidence over trust.** Every state change is written to a hash-chained audit log that
  any party can independently verify.
- **Modular.** Each module below is an independently testable slice with its own DB tables,
  services, API routes and UI feature folder.

---

## 2. Threat model

### 2.1 Assets

- Signed artifacts (documents, code, API payloads) and their signatures.
- X.509 certificates, certificate chains, and the CA trust store.
- Private signing keys (out of scope to hold; in scope to detect compromise *signals*).
- The audit trail itself.
- Operator accounts and the detection configuration.

### 2.2 Adversaries

- **External forger** — crafts or replays signatures, presents spoofed certificates.
- **Compromised signer** — legitimate key used for unauthorised signing.
- **Misissuing / rogue CA** — issues certificates for subjects it should not.
- **Downgrade attacker** — forces weak algorithms (MD5, SHA-1, RSA-1024, PKCS#1 v1.5).
- **Store-now-decrypt-later adversary** — harvests today's RSA/ECC-signed material to break with a
  future quantum computer.
- **Malicious insider** — tampers with detection rules, trust anchors, or the audit log.

### 2.3 Detections (delivered by Module 3 rules unless noted)

| # | Threat | Signal |
|---|---|---|
| T01 | Invalid / forged signature | Cryptographic verification fails |
| T02 | Weak digest | MD5 / SHA-1 in signature or certificate |
| T03 | Weak key | RSA < 2048, DSA, ECC curve < 256-bit, RSA exponent = 1 |
| T04 | Padding downgrade | PKCS#1 v1.5 where PSS is policy; MGF/hash mismatch |
| T05 | ECDSA malleability | Signature not low-S; non-canonical DER |
| T06 | Broken chain | Missing issuer, path-length exceeded, name-constraint violation |
| T07 | Untrusted anchor | Chain terminates outside the configured trust store |
| T08 | Expired / not-yet-valid | Signing time outside certificate validity window |
| T09 | Revoked certificate | CRL / OCSP says revoked; or OCSP response stale / unsigned |
| T10 | Self-signed in production context | Leaf == issuer where policy forbids |
| T11 | Key reuse across identities | Same SPKI under multiple distinct subjects |
| T12 | Issuer anomaly | CA not in the allow-list for that subject / domain |
| T13 | Timestamp forgery | No RFC 3161 token, untrusted TSA, or implausible signing time |
| T14 | Replay | Same payload-digest + signature seen again; signature reused on new payload |
| T15 | Verification-failure burst | N invalid signatures from one source in a window (fuzzing / brute force) |
| T16 | Key-usage / EKU mismatch | Cert used for a purpose its extensions forbid |
| T17 | Trust-store tampering | Trust anchor added/removed (audit + alert) |
| T18 | Quantum exposure | Shor-breakable algorithm protecting long-lived / harvestable data (Module 4) |
| T19 | Anomalous event | ML anomaly score above threshold (Module 5, advisory) |

### 2.4 Out of scope (v1)

Key custody / HSM integration, signing on behalf of users, blockchain anchoring of the audit log
(designed for but not built), full Certificate Transparency log auditing (SCT presence check only).

---

## 3. High-level architecture

```
                         ┌────────────────────────────────────────────────┐
                         │              React + TypeScript SPA             │
                         │  SOC dashboard · Quantum Lab · Audit viewer     │
                         └───────────────┬────────────────────────────────┘
                                         │ HTTPS (JWT)            ▲ SSE alert stream
                                         ▼                       │
┌─────────────┐   API key    ┌───────────────────────────────────┴───────────────┐
│ External    │─────────────▶│                  FastAPI (app/)                    │
│ submitters  │  /api/v1/    │  api/v1  ─ auth · signatures · certificates ·      │
│ (CI, PDF    │   ingest     │            detections · threats · quantum · ml ·   │
│  pipelines) │              │            audit · ingest · stream                 │
└─────────────┘              │                        │                          │
                             │   ┌────────────────────┼────────────────────┐     │
                             │   ▼                    ▼                    ▼     │
                             │ services/crypto   services/detection   services/  │
                             │  hashes            engine + rules       quantum   │
                             │  rsa_ecc           correlation          qubo      │
                             │  x509_chain        scoring              annealer  │
                             │  revocation                            pq_risk    │
                             │  pdf_pades / cms / jws                  tuning     │
                             │  weak_algo / trust_store   services/ml  correlation│
                             │                            features            │  │
                             │   services/audit (hash-chain)  anomaly          │  │
                             └───────┬───────────────────────┬────────────────┬──┘
                                     ▼                       ▼                ▼
                             ┌──────────────┐        ┌──────────────┐  ┌───────────┐
                             │ PostgreSQL   │        │ APScheduler  │  │ var/models│
                             │ (SQLite dev) │        │ /Celery+Redis│  │ (ML arts) │
                             └──────────────┘        └──────────────┘  └───────────┘
```

**Request flow (verify a signature):**

1. Client `POST /api/v1/signatures/verify` with the artifact + signature + (optional) cert chain.
2. `services/crypto` computes digests, verifies RSA/ECC math, builds & validates the X.509 path,
   checks revocation, scans for weak parameters → a structured **VerificationResult** with findings.
3. A **VerificationEvent** row is persisted; `services/detection.engine` runs all enabled rules
   (+ optional ML score) → **Findings** and, above severity threshold, **Alerts**.
4. `services/detection.correlation` links the event to an existing or new **Incident**.
5. `services/quantum.pq_risk` computes the **Quantum Exposure Score** for the signature.
6. The audit log records the action; new alerts are pushed to the SSE stream.
7. Response: verdict, findings, QES, alert/incident references.

---

## 4. Module breakdown

Each module has a **Definition of Done (DoD)**: code + migrations + tests + API docs + a UI slice
(where applicable) + seed/demo data.

### Module 0 — Foundation & scaffolding
- Backend: FastAPI app factory, `pydantic-settings` config, async SQLAlchemy engine/session,
  Alembic, structured logging, exception handlers, health/readiness endpoints, CORS, security
  headers middleware.
- Frontend: Vite + React + TS + Tailwind, router, TanStack Query client, API wrapper, base layout
  + theme, error boundary.
- Infra: `docker-compose.yml` (db, backend, frontend), `Dockerfile`s, `.env.example`, `Makefile`,
  GitHub Actions CI (lint + test + build).
- **DoD:** `make dev` runs backend on SQLite + frontend; `docker compose up` runs the stack;
  `/healthz` green; CI passes.

### Module 1 — Identity & access
- `User`, `Role`, `RefreshToken`, `ApiKey` models. Argon2id hashing. OAuth2 password flow →
  JWT access (15 min) + rotating refresh (hashed, reuse-detection). RBAC deps
  (`admin` / `analyst` / `auditor` / `viewer`). Optional TOTP (pyotp). API-key issuance for ingest.
- Endpoints: `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`,
  `POST /auth/totp/enroll|verify`, `GET/POST/DELETE /users`, `GET/POST/DELETE /api-keys`.
- Frontend: login page, TOTP prompt, auth context, protected routes, user-menu, admin → users.
- **DoD:** full auth cycle, RBAC enforced on a sample route, lockout + audit on failed logins.

### Module 2 — Cryptographic core
- `services/crypto`:
  - `hashes.py` — SHA-256/384/512, SHA-3, digest of streams; weak-hash registry.
  - `rsa_ecc.py` — RSA (PSS + PKCS#1 v1.5) and ECDSA/EdDSA verification; low-S enforcement;
    parameter extraction (modulus bits, curve, exponent, padding).
  - `x509_chain.py` — parse (PEM/DER), build path to a trust anchor, validate basic constraints,
    key usage, EKU, name constraints, validity, path length.
  - `revocation.py` — CRL fetch/parse/cache; OCSP request/response with nonce; SSRF guard;
    timeouts; "unknown" handling policy.
  - `pdf_pades.py` (pyHanko), `cms_pkcs7.py`, `jws.py` — envelope parsing → normalised
    signer info + signed digest + signing time + timestamp token.
  - `weak_algo.py` — maps extracted parameters to threat findings T02–T05, T16.
  - `trust_store.py` — CRUD of trust anchors + CA allow-list; every change audited (T17).
- Endpoints: `POST /signatures/verify`, `POST /signatures/verify-document` (multipart),
  `POST /certificates/validate`, `GET /certificates/{id}`, `GET/POST/DELETE /trust-store`.
- Frontend: signature/certificate explorer, verification-detail drawer (chain viewer,
  findings list, raw ASN.1 toggle), trust-store manager.
- **DoD:** passes RFC/NIST signature test vectors; correct verdicts on the `datasets/` samples;
  weak-parameter findings emitted.

### Module 3 — Threat detection engine
- `VerificationEvent`, `Finding`, `DetectionRule`, `Alert`, `Incident` models.
- `services/detection/engine.py` — loads enabled rules, runs each against the event + historical
  context, collects findings, computes a blended **risk score**, opens alerts above threshold.
- `services/detection/rules/` — one file per rule T01–T17 (T18/T19 injected by Modules 4/5).
  Rules declare id, severity, category (MITRE-ish), and a `evaluate(event, ctx) -> Finding|None`.
- `services/detection/correlation.py` — greedy/Louvain baseline incident grouping (quantum
  version added in Module 4).
- `services/detection/scoring.py` — weighted aggregation; weights come from config, tuned by
  Module 4.
- Endpoints: `GET /detections/rules`, `PATCH /detections/rules/{id}` (enable/weight),
  `GET /threats/alerts`, `PATCH /threats/alerts/{id}` (triage), `GET /threats/incidents`,
  `GET /threats/incidents/{id}`.
- Frontend: alert feed, incident kanban + detail, rule-config screen.
- **DoD:** each rule has a positive + negative test; a scripted attack dataset produces the
  expected alerts and one correlated incident.

### Module 4 — Quantum-inspired optimisation
- `services/quantum/`:
  - `qubo.py` — QUBO/Ising model builder (add linear/quadratic terms, constraints as penalties,
    to/from dense matrix, brute-force solver for n ≤ 20 validation).
  - `annealer.py` — Simulated Annealing **and** Simulated Quantum Annealing (path-integral
    Monte-Carlo, transverse-field schedule Γ(t), Trotter slices, restarts, seeded RNG,
    energy-trajectory capture, time-to-solution).
  - `pq_risk.py` — **Quantum Exposure Score** per signature/cert + portfolio **migration-plan
    optimiser** (capacity-constrained scheduling QUBO).
  - `tuning.py` — detection weight/threshold tuning QUBO over labelled history; reports
    before/after precision-recall-F1.
  - `correlation_qubo.py` — max-weight-clique / community QUBO for incident grouping; compared
    to the Module 3 baseline.
- `QuantumRun` model (type, params, input ref, energy trajectory, result, metrics, seed).
- Endpoints: `POST /quantum/pq-risk/score`, `POST /quantum/pq-risk/plan`,
  `POST /quantum/tuning/run`, `POST /quantum/correlation/run`, `GET /quantum/runs`,
  `GET /quantum/runs/{id}`.
- Frontend: **Quantum Lab** — parameter form, live energy-convergence chart, result panels,
  PQC migration heatmap + wave plan, "apply tuned weights" action.
- **DoD:** solver matches brute-force optimum on small instances; tuning improves holdout F1 on
  the sample dataset; runs are reproducible from their stored seed.

### Module 5 — ML anomaly detection (local, optional)
- `services/ml/` — `features.py` (event → vector, versioned schema), `anomaly.py`
  (IsolationForest default, One-Class SVM alt, PCA-reconstruction optional), `registry.py`
  (artifact hash, params, metrics, feature-schema version, active flag).
- `MlModel` registry table; artifacts under `backend/var/models/`.
- Endpoints: `POST /ml/train`, `GET /ml/models`, `POST /ml/models/{id}/activate`,
  `POST /ml/score` (debug). Engine consumes the active model when `ML_ENABLED=true`.
- Frontend: models list, train dialog (time range / dataset), metrics, activate toggle;
  anomaly score shown on event detail.
- **DoD:** trains on `datasets/labeled_events.csv`, injects finding T19, fully inert when disabled.

### Module 6 — Audit logging (tamper-evident)
- `AuditLog` append-only table: `seq, ts, actor_id, actor_type, action, target_type, target_id,
  meta_json, prev_hash, row_hash`. `row_hash = SHA256(canonical_json(core_fields) || prev_hash)`.
- `services/audit/chain.py` — writer (serialised), verifier (recompute chain, report first break),
  optional daily **anchor** row signed with an app Ed25519 key; signed export (JSON + detached sig).
- Middleware + explicit hooks record: auth events, all mutating API calls, trust-store changes,
  rule changes, ML activation, quantum runs.
- Endpoints: `GET /audit` (filter/paginate), `GET /audit/verify`, `GET /audit/export`.
- Frontend: audit viewer with integrity badge (chain OK / broken at seq N), export button.
- **DoD:** tampering with any row is detected and located; export verifies offline.

### Module 7 — SOC dashboard (frontend consolidation)
- Overview page: KPI tiles (events 24h, open alerts by severity, mean time-to-triage, % quantum-
  vulnerable), threat timeline, severity donut, top rules, live alert feed.
- Cross-feature polish: consistent charts (see `dataviz` conventions), empty/loading/error states,
  keyboard nav, responsive down to tablet, light/dark.
- **DoD:** every API resource reachable from the UI; Lighthouse a11y ≥ 90.

### Module 8 — Real-time & integrations
- SSE `GET /stream/alerts` (Redis pub/sub in prod, in-process broker in dev).
- Background jobs: revocation refresh, CRL cache prune, scheduled tuning, retention purge,
  audit anchor. APScheduler in dev; Celery + Redis beat in prod (same task functions).
- `POST /api/v1/ingest/events` and `/ingest/signatures` for external submitters (API key, scoped,
  rate-limited).
- Optional email/Slack notification sink for high-severity alerts (off by default).
- **DoD:** a new alert appears in the UI within 1 s without refresh; ingest respects rate limits.

### Module 9 — Hardening, tests, deployment ✅
- **Request-path hardening:** in-house rate limiter (auth/verify/ingest — `slowapi` was
  dropped, it broke FastAPI signature introspection), full security-header set incl.
  `Cross-Origin-Opener-Policy` / `-Resource-Policy` and a prod CSP, `BodySizeLimitMiddleware`
  (413 over `MAX_UPLOAD_MB + 5`), prod-only `TrustedHostMiddleware` (`ALLOWED_HOSTS`),
  `defusedxml.defuse_stdlib()` at startup, secrets via env / Docker secrets, fail-closed
  weak-`SECRET_KEY` check.
- **Deployment:** `docker-compose.prod.yml` — PostgreSQL + Redis + gunicorn/uvicorn web
  workers + a **dedicated `worker` container** running the scheduler (`python -m
  app.workers.scheduler`, so web workers run `SCHEDULER_ENABLED=false`) + a TLS-terminating
  nginx `edge` (HSTS, TLS 1.2/1.3, SSE-aware). Every service non-root, healthchecked, no
  published ports except the edge. `deploy/nginx/{edge.conf,gen-selfsigned.sh}`.
- **Tests:** backend pytest — 140 tests (crypto vectors, auth, RBAC, every rule, QUBO
  optimality vs brute force, audit tamper-location, SSE delivery, ingest, hardening
  middleware); frontend Vitest. CI also lints `scripts/` and runs an advisory `pip-audit`.
- `scripts/` — `gen_test_pki.py`, `gen_sample_signatures.py` (raw / JWS / CMS / PAdES demo
  artifacts into `datasets/documents/`), `load_test.py` (stdlib-only, RPS + latency
  percentiles); `app.seeds.seed` demo data.
- **Docs:** `README`, `SECURITY.md`, `docs/{API,QUANTUM,THREAT_MODEL,RUNBOOK,DEMO}.md`, `adr/`.
- **DoD:** one-command prod bring-up (`docker compose -f docker-compose.prod.yml up -d`);
  `ruff` + `mypy` + `pytest` green; the demo script in `docs/DEMO.md` runs end to end.

---

## 5. Data model

```
users ──< refresh_tokens
users ──< api_keys
users ──< audit_logs (actor)

trust_anchors                         ca_allowlist_entries

certificates ──< certificate_relations (issuer_id → subject_id)   # built chains
certificates ──1─ spki_fingerprints    # for key-reuse detection (T11)

verification_events >── signatures      # optional stored artifact ref
verification_events ──< findings
verification_events >── certificates    # signer leaf
verification_events ──< quantum_exposure_scores

detection_rules ──< findings (rule_id)
findings ──< alerts (0..1)
alerts >──< incidents (many alerts → one incident)
incidents ──< incident_events (link table to verification_events)

quantum_runs (type, params_json, input_ref, energy_trajectory_json, result_json, metrics_json, seed)

ml_models (algo, params_json, feature_schema_version, artifact_path, artifact_sha256,
           metrics_json, is_active, trained_by, trained_at)

audit_logs (seq PK, ts, actor_id, actor_type, action, target_type, target_id,
            meta_json, prev_hash, row_hash)

app_config (key, value_json, updated_by, updated_at)   # rule weights, thresholds, toggles
```

Key columns on `verification_events`: `id, created_at, source (api|upload|ingest|connector),
source_ref, envelope_type (raw|pdf|cms|jws), algo, hash_alg, key_type, key_bits, curve,
signing_time, tsa_present, tsa_trusted, chain_status, revocation_status, verdict
(valid|invalid|indeterminate), risk_score, anomaly_score, submitter_ip_hash, payload_sha256`.

Every table has `created_at`; mutable tables have `updated_at`. Soft-delete where audit requires
retention. All timestamps UTC.

---

## 6. Security architecture

### 6.1 Authentication
- OAuth2 password grant → **JWT access token** (HS256 or RS256, `exp` 15 min, `jti`, `role`,
  `token_use=access`) + **refresh token** (opaque 256-bit, stored only as SHA-256, rotating on
  every use, family-based reuse detection → revoke family + alert).
- Passwords: **Argon2id** (`argon2-cffi`), per-user salt, tuned memory/time cost.
- **TOTP** second factor (`pyotp`), optional per user, enforceable per role. Backup codes hashed.
- Failed-login lockout (exponential backoff per account + per IP hash), all attempts audited.

### 6.2 Authorisation
- **RBAC**: `admin` (everything, user mgmt), `analyst` (triage, run quantum/ML, edit rules),
  `auditor` (read + audit verify/export, no mutation), `viewer` (read-only dashboards).
- Enforced by FastAPI dependencies (`require_role(...)`, `require_perm(...)`); object-level checks
  on incident assignment and API-key ownership.

### 6.3 API keys (ingest)
- 32-byte random, shown once, stored as SHA-256 with a visible non-secret prefix.
- Scoped (`ingest:events`, `ingest:signatures`), independently rate-limited and revocable,
  last-used timestamp tracked.

### 6.4 Audit log (tamper-evident)
- Append-only, single-writer serialised. `row_hash = SHA256(canonical_json({seq, ts, actor_id,
  actor_type, action, target_type, target_id, meta_json}) || prev_hash)`.
- `GET /audit/verify` recomputes the whole chain and returns `{ok, checked, break_at}`.
- Optional daily **anchor**: a row whose `meta` holds the running head hash, signed with an app
  **Ed25519** key; `GET /audit/export` returns the range + detached signature for offline proof.
- Design hook (not v1): publish the daily anchor hash to a public blockchain / OpenTimestamps.

### 6.5 Cryptographic hygiene
- Primitives only from `cryptography`. RSA verified with explicit padding object; **ECDSA low-S**
  enforced; non-canonical DER rejected. Unknown/curve-too-small/exponent=1 → hard finding.
- Trust anchors are configuration, never inferred from the artifact under test.
- OCSP/CRL/TSA fetches: allow-list of schemes, **deny RFC 1918 / link-local / loopback**, DNS
  re-bind guard, 5 s timeout, 1 MB cap, response signature verified, results cached.

### 6.6 Transport & platform
- Nginx TLS termination in prod; **HSTS**, **CSP** (`default-src 'self'`), `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` minimal.
- Strict CORS allow-list (env-driven). Refresh token in `Secure; HttpOnly; SameSite=Strict` cookie;
  access token in memory only (never `localStorage`).
- `slowapi` rate limits on `/auth/*`, `/ingest/*`, `/signatures/verify*`.
- Upload limits: max size, content-type allow-list, streamed hashing, stored encrypted at rest
  (AES-GCM, key from env) when `STORE_ARTIFACTS=true`.

### 6.7 Secrets & config
- All secrets via environment / `.env` (git-ignored) / Docker secrets. `SECRET_KEY`,
  `DATABASE_URL`, `AUDIT_SIGNING_KEY`, `ARTIFACT_ENC_KEY`, optional `REDIS_URL`, `SMTP_*`,
  `SLACK_WEBHOOK`. `.env.example` documents every variable. Containers run as non-root.

### 6.8 Input validation
- Pydantic v2 strict models on every request; `defusedxml` for XML-DSig / any XML; explicit
  max lengths; reject unexpected fields.

---

## 7. Quantum-inspired subsystem

> **"Quantum-inspired" = classical algorithms derived from quantum mechanics, run on a normal CPU.**
> No quantum hardware or quantum SDK. Everything is NumPy. Every run is seeded and reproducible,
> and small instances are checked against brute force.

### 7.1 QUBO / Ising core (`qubo.py`, `annealer.py`)

- **Model:** minimise `E(x) = xᵀ Q x`, `x ∈ {0,1}ⁿ`. Ising form via `x = (1 + s) / 2`,
  `s ∈ {−1, +1}ⁿ`, giving `E(s) = sᵀ J s + hᵀ s + const`.
- **Constraints** are quadratic penalties, e.g. "exactly one": `λ (Σ xᵢ − 1)²`, with `λ` chosen
  above the largest objective swing.
- **Simulated Annealing (SA):** Metropolis spin flips, geometric temperature schedule
  `T_k = T₀ αᵏ`, `R` restarts, best-of captured.
- **Simulated Quantum Annealing (SQA):** discrete-time path-integral Monte Carlo — `P` Trotter
  replicas coupled along imaginary time with strength
  `J⊥ = −(P / 2β) ln tanh(β Γ / P)`; transverse field `Γ(t)` swept high→low. Captures quantum
  tunnelling behaviour classically; often escapes local minima SA gets stuck in.
- **Outputs:** best bitstring, best energy, full energy trajectory (for the convergence chart),
  time-to-solution, and `optimal` / `gap` when `n ≤ 20` (brute force).

### 7.2 Hero — Quantum-risk scoring (`pq_risk.py`)

**Per-signature Quantum Exposure Score (QES ∈ [0, 100]):**

| Sub-factor | Basis |
|---|---|
| `algo_factor` | RSA / DSA / ECDSA / ECDH / EdDSA → Shor-breakable ≈ 1.0. ML-DSA (Dilithium), SLH-DSA (SPHINCS+), LMS/XMSS → ≈ 0. |
| `strength_factor` | RSA bits / ECC curve → effective classical bits → interpolated against published CRQC resource estimates (logical qubits, code cycles). Assumption set (`qc_year`, `qubit_growth`, `overhead`) is configurable and shown. |
| `longevity_factor` | Required trust lifetime of the signed data (contract retention, code-signing horizon, legal-hold years) → the "how long must this stay safe" axis of HNDL. |
| `exposure_factor` | Is the artifact public / transmitted / archived where it can be harvested now. |

`QES = 100 · (1 − ∏ (1 − wᵢ · subfactorᵢ))`, weights `wᵢ` configurable; formula and inputs are
rendered in the UI so the score is explainable, not a black box.

**Portfolio migration planner:** given `N` signing identities with `QES`, business criticality,
inter-dependencies, and a per-sprint migration **capacity**, build a scheduling QUBO that assigns
each identity to a migration wave `1..W` minimising **cumulative risk-exposure-time**
(`Σ QESᵢ · wave(i)`) subject to per-wave capacity and "migrate a dependency no later than its
dependents". Solver → recommended wave plan; UI → PQC migration **heatmap** + wave timeline.

### 7.3 Detection tuning (`tuning.py`)

- Variables: one-hot `x_{r,l}` = rule `r` takes weight level `l` (levels e.g. `{0, .5, 1, 2}`),
  plus one-hot threshold bins.
- Objective from labelled history: reward configurations whose weighted firing separates
  malicious from benign events (linear terms from per-rule TP/FP rates, quadratic terms rewarding
  complementary rule pairs, penalising redundant highly-correlated pairs).
- Constraint: exactly one level per rule, one threshold bin.
- Output: new weight vector + threshold → previewed with before/after precision / recall / F1 on a
  holdout split, then `apply` writes them to `app_config` (audited).

### 7.4 Threat correlation (`correlation_qubo.py`)

- Graph `G`: nodes = events in a sliding window; edge weight `w_ij` = similarity (shared SPKI,
  shared submitter-IP hash, same document family, temporal proximity, overlapping finding types).
- Select node subset `S` maximising `Σ_{i,j∈S} w_ij − γ|S|` (γ = resolution) → a cohesive
  incident; repeat on the residual graph. Compared against the greedy/Louvain baseline; UI shows
  both groupings and the cohesion score.

### 7.5 API & jobs

`POST /quantum/pq-risk/score`, `/quantum/pq-risk/plan`, `/quantum/tuning/run`,
`/quantum/correlation/run`, `GET /quantum/runs`, `GET /quantum/runs/{id}`. Scheduled nightly
tuning + a portfolio re-score job (Module 8).

---

## 8. ML anomaly detection

- **Optional and local.** `ML_ENABLED=false` by default; when off, no model is loaded and no
  feature vectors are computed — zero runtime cost, zero dependency in the hot path.
- **Features** (`features.py`, versioned): encoded algo / hash / key-type, key bits, curve id,
  chain depth, days-to-expiry, revocation-check latency, per-category finding counts, verify
  latency, payload-size bucket, hour-of-day, submitter-IP rolling novelty, signer-key age,
  first-seen flags.
- **Models** (`anomaly.py`): IsolationForest (default), One-Class SVM (alt), optional PCA
  reconstruction-error scorer. scikit-learn; trained on-box over an operator-chosen time range or
  `datasets/labeled_events.csv`.
- **Lifecycle**: `POST /ml/train` → artifact in `backend/var/models/` + `ml_models` registry row
  (params, metrics, feature-schema version, SHA-256). `POST /ml/models/{id}/activate` swaps the
  active model. The detection engine blends the active model's score into `risk_score` with a
  configurable weight and can raise advisory finding **T19**. Never overrides a hard crypto fail.
- **Governance**: model metrics, training window and feature-schema version are shown in the UI;
  activation is audited.

---

## 9. Technology stack & rationale

| Layer | Choice | Why |
|---|---|---|
| Backend framework | **FastAPI** + Uvicorn (Gunicorn in prod) | Async, Pydantic validation, OpenAPI for free |
| ORM / migrations | **SQLAlchemy 2 (async)** + **Alembic** | Mature, explicit, DB-portable (SQLite↔Postgres) |
| Validation / settings | **Pydantic v2** / `pydantic-settings` | One model layer, strict parsing, env config |
| Crypto | **`cryptography`**, **pyHanko** (PDF), `asn1crypto` | Audited primitives; pyHanko is the reference PAdES validator |
| Auth | `pyjwt`, `argon2-cffi`, `pyotp` | Standard, well-reviewed building blocks |
| Quantum-inspired | **NumPy only** | Local, no heavy SDK; full control; reproducible |
| ML | **scikit-learn** | Local, CPU, IsolationForest/OCSVM are the right tools; optional |
| Rate limiting | `slowapi` | Simple; in-memory dev, Redis prod |
| Logging | `structlog` | Structured JSON logs, request-id binding |
| DB | **PostgreSQL 16** (prod) / **SQLite** (dev) | Postgres for concurrency/JSONB; SQLite for zero-setup dev |
| Task queue | **APScheduler** (dev) / **Celery + Redis** (prod) | Same task fns; light locally, robust in prod |
| Frontend | **React 18 + TypeScript + Vite** | Required stack; fast dev server, typed end-to-end |
| Styling | **Tailwind CSS** + Radix primitives | Utility-first, accessible primitives, dark SOC theme |
| Server state | **TanStack Query** | Caching, background refetch, less boilerplate |
| Charts | **Recharts** | Declarative, sufficient for SOC visuals; themable |
| Routing | **React Router 6** | Standard |
| Tests | **pytest** / **Vitest + Testing Library** / **Playwright** | Unit + component + E2E |
| Container | **Docker** + Compose; Nginx | Required; reproducible; Nginx serves SPA + proxies API |
| CI | **GitHub Actions** | Lint, test, build on every push |

---

## 10. Repository structure

```
Saitej/
├── README.md  LICENSE  .gitignore  .env.example  .editorconfig  Makefile
├── docker-compose.yml            # dev-ish full stack (Module 0)
├── docker-compose.prod.yml       # hardened prod stack (Module 9)
├── docs/
│   ├── ARCHITECTURE.md           # this document
│   ├── API.md                    # generated route reference (per module)
│   ├── QUANTUM.md                # deep dive: QUBO formulations, solver params (Module 4)
│   ├── THREAT_MODEL.md           # expanded §2 (Module 9)
│   └── adr/                      # architecture decision records
├── backend/
│   ├── pyproject.toml  requirements*.txt  Dockerfile  alembic.ini  .env.example
│   ├── app/
│   │   ├── main.py               # app factory, middleware, router mount
│   │   ├── core/                 # config, security, logging, rate_limit, exceptions
│   │   ├── db/                   # base, session, migrations/
│   │   ├── models/               # SQLAlchemy models (one file per aggregate)
│   │   ├── schemas/              # Pydantic DTOs
│   │   ├── api/
│   │   │   ├── deps.py           # auth/db/rbac dependencies
│   │   │   └── v1/               # auth, users, signatures, certificates, detections,
│   │   │                         # threats, quantum, ml, audit, ingest, stream
│   │   ├── services/
│   │   │   ├── crypto/           # hashes, rsa_ecc, x509_chain, revocation,
│   │   │   │                     # pdf_pades, cms_pkcs7, jws, weak_algo, trust_store
│   │   │   ├── detection/        # engine, rules/, correlation, scoring
│   │   │   ├── quantum/          # qubo, annealer, pq_risk, tuning, correlation_qubo
│   │   │   ├── ml/               # features, anomaly, registry
│   │   │   ├── audit/            # chain
│   │   │   └── notifications/    # email/slack sink (optional)
│   │   ├── workers/              # scheduler (APScheduler) + tasks (Celery)
│   │   └── seeds/                # seed.py — demo users, trust anchors, sample events
│   └── tests/                    # crypto/ api/ detection/ quantum/
├── frontend/
│   ├── package.json  tsconfig.json  vite.config.ts  index.html
│   ├── tailwind.config.ts  postcss.config.js  Dockerfile  nginx.conf  .env.example
│   └── src/
│       ├── main.tsx  App.tsx  router.tsx
│       ├── lib/                  # api client, auth context, query client, formatters
│       ├── components/           # ui/ (primitives), charts/, layout/
│       ├── features/             # auth, dashboard, signatures, certificates,
│       │                         # threats, quantum, audit, admin
│       ├── hooks/  types/  styles/
├── datasets/
│   ├── certs/                    # demo CA + leaf certs, CRLs
│   ├── documents/                # sample signed PDFs / CMS / JWS
│   └── labeled_events.csv        # for tuning + ML
├── scripts/                      # gen_test_pki.py, gen_sample_signatures.py, load_test.py
└── .github/workflows/ci.yml
```

---

## 11. API surface

All under `/api/v1`. `A`=admin `N`=analyst `U`=auditor `V`=viewer `K`=API key.

| Method & path | Roles | Purpose |
|---|---|---|
| `POST /auth/login` | – | Password (+TOTP) → tokens |
| `POST /auth/refresh` | – | Rotate refresh → new access |
| `POST /auth/logout` | any | Revoke refresh family |
| `GET /auth/me` | any | Current identity + role |
| `POST /auth/totp/enroll` · `/verify` | any | Enrol / confirm TOTP |
| `GET/POST/DELETE /users` | A | User management |
| `GET/POST/DELETE /api-keys` | A,N | Ingest key lifecycle |
| `POST /signatures/verify` | N,V,K | Verify raw signature + params |
| `POST /signatures/verify-document` | N,V,K | Verify PDF / CMS / JWS upload |
| `GET /signatures` · `/signatures/{id}` | N,U,V | Browse verification events |
| `POST /certificates/validate` | N,V,K | Validate a cert / chain |
| `GET /certificates` · `/certificates/{id}` | N,U,V | Browse certificates |
| `GET/POST/DELETE /trust-store` | A | Trust anchors + CA allow-list |
| `GET /detections/rules` · `PATCH /detections/rules/{id}` | N (A to disable) | Rule config |
| `GET /threats/alerts` · `PATCH /threats/alerts/{id}` | N,U,V (patch N) | Alert triage |
| `GET /threats/incidents` · `/{id}` | N,U,V | Incident board + detail |
| `POST /quantum/pq-risk/score` · `/plan` | N,V | QES + migration plan |
| `POST /quantum/tuning/run` · `POST /quantum/tuning/apply` | N (apply A) | Tune + apply weights |
| `POST /quantum/correlation/run` | N | Re-correlate a window |
| `GET /quantum/runs` · `/{id}` | N,U,V | Run history + trajectories |
| `POST /ml/train` · `GET /ml/models` · `POST /ml/models/{id}/activate` | N (activate A) | ML lifecycle |
| `GET /audit` · `/audit/verify` · `/audit/export` | U,A | Audit trail + integrity |
| `POST /ingest/events` · `/ingest/signatures` | K | External submission |
| `GET /stream/alerts` | N,U,V | SSE live alert feed |
| `GET /healthz` · `/readyz` | – | Liveness / readiness |

---

## 12. Deployment

### Dev (this machine, today)
```
make dev           # backend: uvicorn + SQLite (./backend/var/dev.db) ; frontend: vite
```
No Docker, no Postgres, no Redis required. APScheduler runs jobs in-process. SSE uses an
in-memory broker. `ML_ENABLED=false`.

### Prod / demo
```
docker compose up --build          # db (Postgres16) + backend + frontend(Nginx)
docker compose -f docker-compose.prod.yml up -d   # + Redis + Celery worker/beat + TLS
```
`.env` supplies `DATABASE_URL`, `SECRET_KEY`, `AUDIT_SIGNING_KEY`, `ARTIFACT_ENC_KEY`,
`CORS_ORIGINS`, optional `REDIS_URL`, `SMTP_*`, `SLACK_WEBHOOK`. Migrations run on container
start (`alembic upgrade head`). Containers run as non-root; secrets via Docker secrets in prod.

### Environment matrix

| Var | Dev default | Prod |
|---|---|---|
| `APP_ENV` | `dev` | `prod` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./var/dev.db` | `postgresql+asyncpg://…` |
| `SECRET_KEY` | dev-only literal | Docker secret |
| `ACCESS_TOKEN_TTL` / `REFRESH_TOKEN_TTL` | 15m / 14d | 15m / 7d |
| `ML_ENABLED` | `false` | operator choice |
| `REDIS_URL` | unset (in-proc) | `redis://redis:6379/0` |
| `OUTBOUND_REVOCATION` | `false` (offline) | operator choice |
| `STORE_ARTIFACTS` | `false` | operator choice |

---

## 13. Observability & testing

- **Logging:** `structlog` JSON, request-id + actor bound per request; auth + security events at
  `warning`+.
- **Metrics:** `/metrics` (Prometheus) — request latency, verify outcomes, alerts opened, quantum
  run duration, queue depth.
- **Health:** `/healthz` (process), `/readyz` (DB + migrations + optional Redis).
- **Testing:**
  - Backend `pytest`: crypto against RFC 6979 / NIST CAVP vectors; auth + RBAC matrix; each
    detection rule (+/-); QUBO solver vs brute force; audit tamper detection; API contract tests.
  - Frontend `Vitest` + Testing Library: components, hooks, auth guard.
  - `Playwright`: login → verify document → see alert → open incident → run quantum tuning →
    verify audit chain.
  - CI gates: `ruff` + `mypy` + `pytest --cov` (≥ 85% services), `eslint` + `tsc` + `vitest`,
    `docker build`.

---

## 14. Build sequence

```
M0 Foundation ──▶ M1 Auth ──▶ M2 Crypto core ──▶ M3 Detection engine ──┐
                                                                        ▼
        M6 Audit ◀── M5 ML (optional) ◀── M4 Quantum-inspired optimisation
              │
              ▼
        M7 SOC dashboard ──▶ M8 Real-time & integrations ──▶ M9 Hardening + tests + deploy
```

Each module is delivered complete (code + migration + tests + docs + UI slice + seed data) and
reviewed before the next begins. Modules 2–6 each extend the running app; nothing is stubbed.

---

## 15. Requirement traceability

| Problem-statement requirement | Where it is satisfied |
|---|---|
| Quantum-inspired | Module 4 — SA/SQA over QUBO/Ising, three applications, reproducible, brute-force-checked |
| Cyber threat detection | Module 3 — 17 deterministic rules + correlation + risk scoring; Module 5 ML anomaly (advisory) |
| Digital signature security | Module 2 — RSA/ECC/EdDSA verification, PAdES/CMS/JWS, X.509 chain + revocation |
| Strong cryptography (RSA, ECC, SHA-256, certificate validation) | Module 2 — `cryptography` + pyHanko; low-S, PSS, full path validation, CRL/OCSP |
| Secure auth | Module 1 — Argon2id, JWT + rotating refresh with reuse detection, RBAC, optional TOTP |
| Audit logs | Module 6 — append-only hash-chained log, verifier + signed export |
| Modern SOC dashboard | Modules 7 — KPI tiles, live feed, incident kanban, Quantum Lab, audit viewer |
| Quantum-inspired optimisation | Module 4 — detection tuning, migration planning, correlation |
| Optional ML for anomaly detection only | Module 5 — local scikit-learn, off by default, advisory only |
| Modular code, clear file structure | §10 — feature-foldered frontend, service-layered backend, one module per slice |
| React + TypeScript / FastAPI / PostgreSQL / Docker | §9, §12 — exactly this stack; SQLite only as a dev convenience |
| No placeholders | §14 — every module ships working code + tests + seed data |
| Security best practices | §6 — headers, rate limits, SSRF guards, secrets hygiene, non-root containers, dep audit |

---

*Next: Module 0 — Foundation & scaffolding. This document is revised as decisions change; see
`docs/adr/` for the rationale behind each significant choice.*

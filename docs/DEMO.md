# Demo Script — Egreen Quanta

A 9–10 minute walkthrough for the SIH 2026 evaluation (Problem Statement 141:
*Quantum-Inspired Cyber Threat Detection for Digital Signature Security*).

The arc: **verify → detect → correlate → quantum-prioritise → prove it's tamper-evident.**

---

## 0. Before the judges arrive (5 min)

```bash
# one terminal
make dev-backend        # http://localhost:8000  (SQLite, autoreload)
# another
make seed               # demo users, trust anchors, a few historical events
make dev-frontend       # http://localhost:5173

python scripts/gen_test_pki.py            # datasets/certs/  — demo CA + leaves
python scripts/gen_sample_signatures.py   # datasets/documents/ — ready-to-paste bodies
```

Open `http://localhost:5173`, log in as **`admin@egreen.local` / `EgreenQuanta!2026`**.
Leave the app on the **Overview** page. Have `datasets/documents/` open in a file
browser.

> If anything is wrong: `curl -s localhost:8000/api/v1/readyz` should say
> `"database":"ok"`. Restart `make dev-backend` if not.

---

## 1. Framing (45 s) — *Overview page*

> "Digital signatures are the trust anchor for contracts, software updates and
> PKI. Two problems: attackers actively forge and downgrade them, and a future
> quantum computer retro-actively breaks today's RSA and ECC. Egreen Quanta is a
> SOC console for exactly that surface."

Point at the KPI tiles (events, open alerts, incidents), the severity donut, the
timeline, and the **PQC exposure** panel. "All live — seeded with a bit of
history so it's not empty."

## 2. Verify a good signature (1 min) — *Signatures*

- **Signatures → Verify raw**.
- Paste `datasets/documents/raw/rsa-pss.json` (data, signature, cert chain).
- Submit. Verdict **valid**, algorithm `sha256-rsa-pss`, chain **trusted** (the
  demo root is a seeded anchor), risk score low.

> "Real verification — `cryptography` primitives, our own strict X.509 chain
> builder, not a library black box."

## 3. Catch a forgery + a downgrade (2 min) — *Signatures → Threats*

- Verify `datasets/documents/raw/tampered.json` → verdict **invalid**, finding
  **T01**. "One byte of the payload changed; signature no longer matches."
- Verify `datasets/documents/raw/rsa-pkcs1v15.json` → still valid, but note the
  finding for **PKCS#1 v1.5 where PSS is policy** (T04), plus weak-parameter
  findings if you use the 1024-bit leaf.
- Go to **Threats → Alerts**. The forgery is here as an alert. Open the drawer:
  rule, severity, the offending event, the risk-score breakdown (noisy-OR over
  rule weights).

> "19-rule catalogue T01–T19: forged, weak digest, weak key, padding downgrade,
> ECDSA malleability, broken/untrusted chain, expired, revoked, key reuse,
> replay, burst… Each is one small, testable rule file."

## 4. Replay + burst → an incident (1.5 min) — *Threats → Incidents*

- Re-submit `tampered.json` two or three more times quickly.
- **Threats → Alerts**: a **replay (T14)** alert appears — same payload digest and
  signature seen again — and after a few, a **burst (T15)**.
- **Threats → Incidents**: those alerts are **correlated into one incident**
  (greedy correlation by source / key / time). "Analysts triage one incident, not
  twenty alerts."

## 5. Quantum-inspired prioritisation (2.5 min) — *Quantum Lab*

This is the differentiator. Four tabs.

**a) Quantum Exposure Score** — pick `RSA-2048`, long retention, public/archived
context → score lands in the **immediate** band. Switch algorithm to
**ML-DSA (Dilithium)** → score collapses to the **ok** band.

> "`algo_factor` is a hard gate: Shor-breakable (RSA/ECC/EdDSA) ≈ 1, PQC ≈ 0.
> Then strength, data longevity and harvest exposure scale it. This is the
> harvest-now-decrypt-later axis, quantified."

**b) Migration planner** — run it. A **scheduling QUBO** orders which
certificates / services to migrate first under a resource budget; solved with
**simulated annealing + simulated quantum annealing** (path-integral Monte Carlo)
racing each other. Show the **energy trajectory** chart going down.

**c) Detection tuning** — run. A QUBO over rule weights against labelled history;
it proposes weights, and we only apply them if F1 actually improves (guarded).

**d) Correlation** — run on a window; a densest-subgraph QUBO regroups alerts.

> "Pure NumPy, no quantum hardware, seeded and reproducible. On small instances
> we verified the annealers hit the brute-force optimum. `docs/QUANTUM.md` has
> the maths."

## 6. Tamper-evident audit (1.5 min) — *Audit Log*

- **Audit Log**: every login and every mutating request, hash-chained
  (`row_hash = SHA256(canonical(row) ‖ prev_hash)`).
- Click **Verify integrity** → `ok: true`.
- Then, for effect, from a shell:

```bash
sqlite3 backend/var/dev.db "UPDATE audit_log SET action='(edited)' WHERE seq=3;"
```

- **Verify integrity** again → `ok: false`, **broken at seq 3**. "It doesn't just
  say 'tampered' — it points at the exact row. Optional Ed25519 anchor lets you
  prove it to a third party."
- (Re-seed afterwards: `make seed`.)

## 7. Close (30 s)

> "React + FastAPI + Postgres, Docker-deployable, `docker-compose.prod.yml` with a
> TLS edge. Argon2id, rotating refresh tokens with reuse detection, RBAC,
> tamper-evident audit, SSRF-guarded revocation, defused XML. 140 backend tests
> green. Verify, detect, correlate, and prioritise for the quantum transition —
> in one console."

---

## Quick reference

| Thing | Value |
|---|---|
| Frontend | `http://localhost:5173` |
| API docs | `http://localhost:8000/docs` |
| Login | `admin@egreen.local` / `EgreenQuanta!2026` (also `analyst@`, `auditor@`, `viewer@`) |
| Sample bodies | `datasets/documents/` (+ `manifest.json` says which endpoint each is for) |
| Demo PKI | `datasets/certs/` |
| Reset demo data | `make seed` |

## If a step fails

| Problem | Do this |
|---|---|
| Blank dashboard | `make seed`, refresh |
| Login 500 | restart `make dev-backend`; check `readyz` |
| "live" dot offline (Topbar) | SSE didn't connect — harmless for the demo; alerts still refresh on navigation |
| Quantum run slow | lower sweeps in the form, or just talk over the energy chart |
| Audit tamper demo | make sure you edited `backend/var/dev.db` (dev SQLite), not a stale copy |

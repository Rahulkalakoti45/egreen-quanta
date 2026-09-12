# 2. Core technical choices

- Status: accepted
- Date: 2026-09-09
- Supersedes: –

## Context

SIH PS-141 mandates React + TypeScript, Python FastAPI, PostgreSQL, and Docker. The development
machine currently has Python 3.12 and Node 24 but no Docker daemon and no PostgreSQL server. The
team wants to iterate today and still demo a production-shaped stack.

## Decisions

1. **DB portability: SQLite in dev, PostgreSQL in prod.** SQLAlchemy 2 + Alembic, no
   Postgres-only SQL in application code; `JSONB` accessed via the portable `JSON` type. Lets the
   backend run on the current machine with zero setup while `docker compose` provides Postgres 16
   for the real target.

2. **Quantum-inspired solver in pure NumPy.** Simulated Annealing and Simulated Quantum Annealing
   (path-integral Monte Carlo) over QUBO/Ising models, implemented from scratch. No `dwave-*`,
   `qiskit`, or other heavy SDK. Rationale: fully local, no dependency risk, complete control of
   the schedule, reproducible from a seed, and small instances are checked against brute force —
   which is exactly what a judge needs to trust the result.

3. **ML is optional and off by default (`ML_ENABLED=false`).** scikit-learn IsolationForest /
   One-Class SVM, trained on-box, advisory only — it never overrides a hard cryptographic verdict.
   Matches the "optional ML only for anomaly detection" wording and the local-first principle.

4. **SSE, not WebSocket, for the live alert feed.** One-directional server→client push is all the
   dashboard needs; SSE is simpler to operate, works through Nginx trivially, and needs no extra
   client library. Redis pub/sub fans out in prod; an in-process broker is used in dev.

5. **APScheduler in dev, Celery + Redis in prod — same task functions.** Background jobs
   (revocation refresh, nightly tuning, retention purge, audit anchoring) are plain functions
   invoked by APScheduler locally and by Celery beat in the hardened stack, so there is one code
   path to test.

6. **Tamper-evident audit log via hash chaining, with an optional Ed25519 daily anchor.** Cheaper
   and dependency-free compared to per-row signatures; the signed daily anchor plus signed export
   gives non-repudiation. A hook is left to publish the anchor hash to a public chain later.

## Consequences

- Application code must avoid DB-engine-specific features; migrations are tested on both engines
  in CI.
- The quantum-inspired module owns its correctness burden (brute-force parity tests, seeded runs).
- Turning ML on is a deliberate operator action, logged to the audit trail.

# Egreen Quanta

**Quantum-Inspired Cyber Threat Detection for Digital Signature Security**
SIH 2026 · Problem Statement 141 · Blockchain & Cybersecurity

A Security Operations Center (SOC) platform for **digital-signature and PKI trust**. It verifies
RSA / ECC / EdDSA signatures and X.509 chains (PAdES, CMS/PKCS#7, JWS), detects signature-security
threats with a rule engine plus optional local ML, and uses a **quantum-inspired optimisation
subsystem** for quantum-risk scoring, detection tuning, and threat correlation — all presented in
a modern dark SOC dashboard with a tamper-evident audit log.

> Full design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Stack

| | |
|---|---|
| Frontend | React 18 · TypeScript · Vite · Tailwind · TanStack Query · Recharts |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · Pydantic v2 |
| Crypto | `cryptography` · pyHanko · `asn1crypto` |
| Quantum-inspired | NumPy (simulated annealing / simulated quantum annealing over QUBO) |
| ML (optional) | scikit-learn — IsolationForest / One-Class SVM, off by default |
| Data | PostgreSQL 16 (prod) · SQLite (dev) |
| Infra | Docker + Compose · Nginx (TLS edge) · Redis + dedicated scheduler worker (prod) · GitHub Actions |

## Modules

| # | Module | Status |
|---|---|---|
| 0 | Foundation & scaffolding | ✅ done — backend + frontend build, lint, typecheck, test green |
| 1 | Identity & access (Argon2id, JWT, RBAC, TOTP) | ✅ done — 25 backend tests, 4 frontend tests, live auth flow verified |
| 2 | Cryptographic core (RSA/ECC, X.509, CRL/OCSP, PAdES/CMS/JWS) | ✅ done — 65 backend tests, verify + trust-store + certificate UI, demo PKI generated |
| 3 | Threat detection engine (19 rules + correlation + scoring) | ✅ done — 83 backend tests, event/alert/incident model, risk scoring, greedy correlation, alert feed + incident kanban + rules config UI, live SOC dashboard |
| 4 | Quantum-inspired optimisation (risk scoring · tuning · correlation) | ✅ done — 104 backend tests; NumPy SA + SQA over QUBO (brute-force-verified), Quantum Exposure Score + PQC migration planner, detection-weight tuning, correlation QUBO, Quantum Lab UI, [docs/QUANTUM.md](docs/QUANTUM.md) |
| 5 | ML anomaly detection (local, optional) | ✅ done — 116 backend tests; scikit-learn IsolationForest / One-Class SVM, 42-feature pipeline, model registry + activation, advisory T19 into the risk engine, off by default (`ML_ENABLED=false`), `scripts/gen_ml_dataset.py` |
| 6 | Audit logging (hash-chained, verifiable) | ✅ done — 127 backend tests; append-only SHA-256 chain, middleware records every mutating request + auth events, tamper-detection verifier (locates the break), Ed25519 anchor + signed export, audit viewer UI |
| 7 | SOC dashboard consolidation | ✅ done — dashboard top-detections + recent-alerts + PQC-exposure panels, light/dark/system theme toggle, mobile nav drawer, skip-link + ARIA pass, token-driven charts |
| 8 | Real-time & integrations (SSE, jobs, ingest API) | ✅ done — 139 backend tests; SSE `/stream/alerts` with live UI updates + toasts, API-key `/ingest/{signatures,events}`, dependency-free async scheduler (audit anchor, retention purge), optional Slack/SMTP notifications |
| 9 | Hardening, tests, deployment | ✅ done — 140 backend tests; request-path hardening (TrustedHost, body-size limit, expanded headers, `defusedxml`), `docker-compose.prod.yml` (Postgres + Redis + dedicated scheduler worker + TLS nginx edge), `scripts/gen_sample_signatures.py` + `scripts/load_test.py`, `SECURITY.md` + `docs/{RUNBOOK,DEMO,API,THREAT_MODEL}.md`, CI lints `scripts/` + advisory `pip-audit` |

## Quick start

### Dev (Python + Node only — no Docker needed)

```bash
make dev
```

Runs the FastAPI backend on SQLite (`backend/var/dev.db`) at `http://localhost:8000` and the Vite
dev server at `http://localhost:5173`. API docs at `http://localhost:8000/docs`.

Seed demo data (users, trust anchors, sample events):

```bash
make seed
```

Demo accounts (dev/test only — all share one fixed password):

| email | password | role |
|---|---|---|
| `admin@egreen.local` | `EgreenQuanta!2026` | admin |
| `analyst@egreen.local` | `EgreenQuanta!2026` | analyst |
| `auditor@egreen.local` | `EgreenQuanta!2026` | auditor |
| `viewer@egreen.local` | `EgreenQuanta!2026` | viewer |

In production (`APP_ENV=prod`) the seeder generates a strong random password per account and
prints it once. Change `SECRET_KEY` and all passwords before any real use.

### Full stack (Docker)

```bash
cp .env.example .env      # then edit secrets
docker compose up --build
```

Frontend on `http://localhost:8080` (Nginx), API proxied at `/api`.

**Production-hardened stack** (PostgreSQL + Redis + a dedicated scheduler worker + a
TLS-terminating nginx edge):

```bash
cp .env.example .env                          # set SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD,
                                              #     ALLOWED_HOSTS, CORS_ORIGINS
sh deploy/nginx/gen-selfsigned.sh your-host   # or drop real certs in deploy/nginx/certs/
docker compose -f docker-compose.prod.yml up -d --build
```

Runbook: [`docs/RUNBOOK.md`](docs/RUNBOOK.md). Demo script: [`docs/DEMO.md`](docs/DEMO.md).

## Repository layout

```
backend/app/{core,db,models,schemas,api,services,workers,seeds}   # service-layered
frontend/src/{lib,components,features,hooks,types,styles}          # feature-foldered
datasets/    # demo CA, signed docs, labelled events
scripts/     # gen_test_pki.py, gen_sample_signatures.py, load_test.py
docs/        # ARCHITECTURE.md, API.md, QUANTUM.md, THREAT_MODEL.md, adr/
```

## Testing

```bash
make test        # backend pytest (140) + frontend vitest
make lint        # ruff + mypy + eslint + tsc
make typecheck   # mypy + tsc only
```

Capacity check against a running stack: `python scripts/load_test.py --scenario verify -n 500 -c 16`.

## Security

See [`SECURITY.md`](SECURITY.md) and [`docs/ARCHITECTURE.md` §6](docs/ARCHITECTURE.md#6-security-architecture).
Highlights: Argon2id, rotating refresh tokens with family-based reuse detection, ranked RBAC,
in-process rate limits (auth / verify / ingest), strict security headers + prod CSP/HSTS,
`TrustedHostMiddleware` + request-body size cap, `defusedxml` at startup, SSRF-guarded revocation
fetches (off by default), tamper-evident SHA-256 audit chain with an integrity verifier, non-root
containers with no published ports behind a TLS edge, secrets via env / Docker secrets, and a
fail-closed check that refuses to boot prod with a weak `SECRET_KEY`.
**Change every secret in `.env.example` before deploying.** Threat model: [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

## License

MIT — see [`LICENSE`](LICENSE).

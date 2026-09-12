# API Reference — Egreen Quanta

Base URL: `{host}/api/v1` (the OpenAPI schema and Swagger UI are served at
`/openapi.json` and `/docs`). All request and response bodies are JSON unless a
route takes `multipart/form-data` for file upload.

---

## Authentication

Two schemes:

| Scheme | Header | Used by |
|---|---|---|
| Bearer (JWT) | `Authorization: Bearer <access_token>` | Interactive console users |
| API key | `X-API-Key: egq_<prefix>_<secret>` | Machine ingest (`/ingest/*`) |

### Token lifecycle

```
POST /api/v1/auth/login      { "email", "password", "totp_code"? }  -> { access_token, refresh_token, expires_in, role }
POST /api/v1/auth/refresh    { "refresh_token" }                    -> new { access_token, refresh_token }
POST /api/v1/auth/logout     { "refresh_token" }                    -> 204   (revokes the whole token family)
GET  /api/v1/auth/me                                                -> current identity + role
```

Access tokens are short-lived (`ACCESS_TOKEN_TTL`, default 15 min). Refresh tokens
**rotate on every use**; presenting a previously-used refresh token is treated as
theft and revokes the entire family. The frontend does this transparently.

### Roles

`admin > analyst > auditor > viewer` (ranked). Each endpoint below lists the
minimum role: **A**dmin, a**N**alyst, a**U**ditor, **V**iewer, api-**K**ey.

---

## Endpoints

### Identity & access

| Method & path | Role | Purpose |
|---|---|---|
| `POST /auth/login` | – | Password (+ TOTP) → tokens |
| `POST /auth/refresh` | – | Rotate refresh → new access |
| `POST /auth/logout` | any | Revoke refresh family |
| `GET /auth/me` | any | Current identity + role |
| `POST /auth/totp/enroll` · `/auth/totp/verify` | any | Enrol / confirm TOTP |
| `GET/POST/PATCH/DELETE /users` | A | User management |
| `GET/POST/DELETE /api-keys` | A, N | Ingest key lifecycle (secret shown once) |

### Cryptographic verification

| Method & path | Role | Purpose |
|---|---|---|
| `POST /signatures/verify` | N, V, K | Verify a raw detached signature + parameters |
| `POST /signatures/verify-document` | N, V, K | Verify a PDF (PAdES) / CMS(PKCS#7) / JWS upload |
| `GET /signatures` · `GET /signatures/{id}` | N, U, V | Browse verification events |
| `POST /certificates/validate` | N, V, K | Validate a certificate / chain |
| `GET /certificates` · `GET /certificates/{id}` | N, U, V | Browse observed certificates |
| `GET/POST/DELETE /trust-store` | A | Trust anchors + CA allow-list (audited, T17) |

`POST /signatures/verify` body:

```jsonc
{
  "data_b64":       "<base64 of the signed bytes, or its digest>",
  "signature_b64":  "<base64 of the detached signature>",
  "hash_alg":       "sha256",            // null for pure EdDSA
  "padding":        "pss",               // "pss" | "pkcs1v15" | null (ECDSA/EdDSA)
  "is_prehashed":   false,
  "certificate_pem": "-----BEGIN CERTIFICATE----- …",   // or public_key_pem
  "public_key_pem":  null,
  "verify_time":    null                 // ISO 8601; defaults to now
}
```

Response (`VerificationOut`, abridged):

```jsonc
{
  "id": 42,
  "verdict": "valid",                    // valid | invalid | indeterminate | error
  "envelope": "raw",
  "signature": { "algorithm": "sha256-rsa-pss", "key_bits": 3072, … },
  "signer":   { "subject": "…", "issuer": "…", "not_after": "…" },
  "chain":    { "status": "trusted", "length": 3 },
  "revocation": { "status": "not_checked" },
  "findings": [ { "id": "T04", "severity": "medium", "detail": "…" } ],
  "risk_score": 18.5,
  "event_id": 42, "alert_id": null, "incident_id": null
}
```

Ready-made sample bodies: `datasets/documents/` (run
`python scripts/gen_sample_signatures.py`).

### Threat detection

| Method & path | Role | Purpose |
|---|---|---|
| `GET /detections/rules` · `PATCH /detections/rules/{id}` | N (A to disable) | Rule catalogue + weight/threshold config |
| `GET /threats/alerts` · `PATCH /threats/alerts/{id}` | N, U, V (patch N) | Alert triage (status, assignee, notes) |
| `GET /threats/incidents` · `GET /threats/incidents/{id}` | N, U, V | Correlated incident board + detail |

### Quantum-inspired optimisation

| Method & path | Role | Purpose |
|---|---|---|
| `POST /quantum/pq-risk/score` | N, V | Quantum Exposure Score for an algo + context |
| `POST /quantum/pq-risk/plan` | N, V | PQC migration plan (scheduling QUBO) |
| `POST /quantum/tuning/run` · `POST /quantum/tuning/apply` | N (apply A) | Tune detection weights, then apply |
| `POST /quantum/correlation/run` | N | Re-correlate a time window (densest-subgraph QUBO) |
| `GET /quantum/runs` · `GET /quantum/runs/{id}` | N, U, V | Solver run history + energy trajectories |

### ML anomaly detection (optional)

| Method & path | Role | Purpose |
|---|---|---|
| `POST /ml/train` | N | Train IsolationForest / One-Class SVM on labelled events |
| `GET /ml/models` | N, U, V | Model registry |
| `POST /ml/models/{id}/activate` | A | Make one model active (single-active) |

Inert unless `ML_ENABLED=true`.

### Audit

| Method & path | Role | Purpose |
|---|---|---|
| `GET /audit` | U, A | Paginated audit trail |
| `GET /audit/verify` | U, A | Walk the hash chain; reports `ok` and the first broken `seq` |
| `GET /audit/export` | U, A | Signed range export (Ed25519 anchor if configured) |

### Real-time & ingest

| Method & path | Role | Purpose |
|---|---|---|
| `GET /stream/alerts` | N, U, V | **SSE** live alert feed (`text/event-stream`) |
| `POST /ingest/signatures` | K | Submit a signature for verification + detection |
| `POST /ingest/events` | K | Submit a pre-computed verification result |

`GET /stream/alerts` emits `: connected`, periodic keepalives, and
`event: <type>\ndata: <json>\n\n` frames. Consume with `EventSource` or a
streaming fetch (the frontend uses the latter for `Authorization` support).

### System

| Method & path | Role | Purpose |
|---|---|---|
| `GET /system/info` | – | Name, environment, DB backend, `ml_enabled`, `outbound_revocation` |
| `GET /api/v1/readyz` | – | Readiness (checks the DB) |
| `GET /healthz` | – | Liveness (no dependencies) |

---

## Errors

Uniform envelope:

```json
{ "error": { "code": "validation_error", "message": "Request validation failed", "details": [ … ] } }
```

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `app_error` / domain code | Bad request |
| 401 | `unauthorized` | Missing / invalid / expired token |
| 403 | `forbidden` | Authenticated but role too low |
| 404 | `not_found` | No such resource |
| 409 | `conflict` | e.g. duplicate email, refresh-token reuse |
| 413 | `payload_too_large` | Body over `MAX_UPLOAD_MB + 5` |
| 422 | `validation_error` | Schema validation failed (`details` has the field errors) |
| 429 | `rate_limited` | See limits below; retry after the window |
| 500 | `internal_error` | Unexpected; message is intentionally generic |

## Rate limits

In-process fixed-window limiter (disabled under `APP_ENV=test`):

| Group | Limit | Routes |
|---|---|---|
| `auth` | 10 / 60 s | `POST /auth/login` |
| `verify` | 120 / 60 s | `POST /signatures/verify*` |
| `ingest` | 600 / 60 s | `POST /ingest/*` |

Login additionally locks an account for `LOGIN_LOCKOUT_SECONDS` after
`LOGIN_MAX_ATTEMPTS` consecutive failures.

## Versioning

The prefix (`/api/v1`) is the version. Breaking changes would ship under a new
prefix; additive fields will not.

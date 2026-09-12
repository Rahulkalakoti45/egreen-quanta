# Security Policy

Egreen Quanta is a security-analysis tool for digital-signature and PKI trust. It
is built to be run by a SOC team on data they are authorised to inspect. This
document covers how the project itself is hardened and how to report a weakness.

## Reporting a vulnerability

This is a Smart India Hackathon 2026 project (Problem Statement 141). There is no
public bug-bounty. If you find a security issue:

1. **Do not** open a public issue with exploit details.
2. Email the maintainers (see repository owner) with a description, affected
   version / commit, and a proof-of-concept if you have one.
3. Expect an acknowledgement within a few days and a fix or mitigation plan.

## Supported versions

The `main` branch is the only supported line. Each module tag (`Module N …`) is a
checkpoint, not a maintained release.

## Hardening baseline

The application ships secure-by-default. The table is the intended production
posture; `APP_ENV=prod` enforces the items marked **fail-closed**.

| Area | Control |
|---|---|
| Passwords | Argon2id (`argon2-cffi`), per-user salt, tunable time/memory cost |
| Sessions | Short-lived JWT access tokens; refresh tokens rotate on use with **family-based reuse detection** (a replayed refresh token revokes the whole family) |
| MFA | Optional TOTP (`pyotp`), enrol + confirm flow |
| AuthZ | RBAC with ranked roles (`admin > analyst > auditor > viewer`); every route declares its minimum role |
| Ingest | Scoped API keys (`egq_<prefix>_<secret>`), shown once, hashed at rest, per-scope |
| Secrets | From env / Docker secrets. **Fail-closed:** prod refuses to boot with the shipped dev `SECRET_KEY` or one under 32 chars |
| Transport | TLS terminates at the nginx `edge` container; HSTS (2 yr), TLS 1.2/1.3 only, modern cipher suite |
| HTTP headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`; CSP + HSTS added in prod |
| Host header | `TrustedHostMiddleware` in prod when `ALLOWED_HOSTS` is set |
| Request size | `BodySizeLimitMiddleware` rejects bodies over `MAX_UPLOAD_MB + 5` with 413; nginx `client_max_body_size 30m` |
| Rate limits | In-process limiter on auth (`10/min`), verify (`120/min`), ingest (`600/min`) |
| SSRF | CRL/OCSP/TSA fetches are **off by default** (`OUTBOUND_REVOCATION=false`); when on, private/link-local/loopback targets are blocked, response size and time are capped |
| XXE / entity expansion | `defusedxml.defuse_stdlib()` at startup before any XML parser is touched |
| Audit | Append-only SHA-256 hash chain; every mutating request + auth event recorded; `/audit/verify` locates the exact broken row; optional Ed25519 anchor + signed export |
| Containers | Non-root user, multi-stage builds, no host ports except the edge, per-service healthchecks |
| Crypto hygiene | Constant-time verification via `cryptography`; MD5/SHA-1, RSA < 2048, non-low-S ECDSA, PKCS#1 v1.5-where-PSS-expected all flagged as findings |

## Cryptography notes

- Signature verification uses the `cryptography` library primitives; no hand-rolled
  bignum or padding code.
- The X.509 chain builder is implemented in-repo (`services/crypto/x509_chain.py`)
  and is deliberately strict: self-signed non-anchors are `untrusted`, path-length
  and validity windows are enforced, SPKI cycles are broken.
- The **quantum-inspired** subsystem is classical NumPy (simulated annealing /
  simulated quantum annealing over QUBO). It does no cryptography and never
  weakens a verdict — it only scores and prioritises.

## What this tool is not

- Not a CA or a signing service — it verifies, it does not issue or sign
  (the `scripts/gen_*` helpers produce throwaway demo material only).
- Not an investment or migration mandate — the PQC planner is decision support.
- Not a replacement for an HSM-backed PKI or a SIEM.

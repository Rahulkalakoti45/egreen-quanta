# Threat Model — Egreen Quanta

Scope: the digital-signature / PKI trust problem the product analyses **and** the
product itself. This is a working document; the authoritative narrative lives in
[`ARCHITECTURE.md` §2](ARCHITECTURE.md#2-threat-model).

---

## 1. Assets

| # | Asset | Why it matters |
|---|---|---|
| A1 | Verification verdicts & risk scores | Downstream decisions (accept a contract, trust a build) depend on them |
| A2 | Trust store (anchors + CA allow-list) | The root of every chain decision; tampering silently changes all verdicts |
| A3 | Audit log | Evidence; must be tamper-evident to be worth anything |
| A4 | User credentials & sessions | Access to the console and its data |
| A5 | Ingest API keys | Machine submission path into detection |
| A6 | ML models & quantum run history | Influence prioritisation; poisoning shifts attention |
| A7 | Submitted artifacts / signatures | May be sensitive (contracts, code-signing blobs) |

## 2. Trust boundaries

```
 Internet ──► edge (nginx, TLS)
                 │
     ┌───────────┼──────────────┐
     ▼           ▼              ▼
  frontend    backend (API) ──► worker (scheduler)
  (static)       │  │  │
                 │  │  └──► PostgreSQL      (A1–A6)
                 │  └─────► Redis           (broker/cache, prod)
                 └────────► outbound CRL/OCSP  ◄─ OFF by default (SSRF surface)
```

- **B1 Internet → edge:** untrusted. TLS, HSTS, host allow-list, body-size cap.
- **B2 edge → backend:** trusted network inside compose; backend still authнenticates every request.
- **B3 backend → DB/Redis:** credentialed; no host ports published in prod.
- **B4 backend → outbound revocation:** backend → arbitrary URL. Highest-risk
  egress. Disabled unless `OUTBOUND_REVOCATION=true`; then private ranges blocked,
  size/time capped.
- **B5 API-key client → /ingest:** semi-trusted; scoped keys, rate-limited.

## 3. Adversaries

| Adversary | Capability | Primary mitigations |
|---|---|---|
| Forger | Crafts signatures / certs to be accepted as valid | Constant-time verification, strict chain build, T01–T13 |
| Downgrade attacker | Pushes weak algorithms / padding / curves | T02–T05, T16; policy comparison in `weak_algo.py` |
| Replay attacker | Re-submits or re-targets a captured signature | History-aware T14 (payload-digest + signature memory), T15 burst |
| Trust-store manipulator | Adds/removes an anchor (insider or compromised admin) | Admin-only + every change audited & alerted (T17) |
| Harvest-now-decrypt-later | Records today, breaks with a future quantum computer | T18 Quantum Exposure Score, PQC migration planner |
| Console attacker | Steals a session, brute-forces login, abuses RBAC gaps | Argon2id, login rate limit + lockout, rotating refresh w/ reuse detection, ranked RBAC |
| Malicious ingest client | Floods or poisons detection via API key | Per-scope keys, `600/min` limit, same rule engine (no bypass) |
| Log tamperer | Edits/deletes audit rows to hide activity | SHA-256 hash chain; `/audit/verify` finds the break; Ed25519 anchor |
| Prompt-injected content | Hostile text inside a submitted artifact | Artifacts are parsed as data only; no eval, no shell, XML parsers defused |

## 4. Detection catalogue (T01–T19)

| ID | Threat | Signal | Delivered by |
|---|---|---|---|
| T01 | Invalid / forged signature | Cryptographic verification fails | M2/M3 |
| T02 | Weak digest | MD5 / SHA-1 in signature or cert | M2 |
| T03 | Weak key | RSA < 2048, DSA, ECC < 256-bit, exponent 1 | M2 |
| T04 | Padding downgrade | PKCS#1 v1.5 where PSS is policy; MGF/hash mismatch | M2 |
| T05 | ECDSA malleability | Not low-S; non-canonical DER | M2 |
| T06 | Broken chain | Missing issuer, path-length, name-constraint | M2 |
| T07 | Untrusted anchor | Chain ends outside the trust store | M2 |
| T08 | Expired / not-yet-valid | Signing time outside validity window | M2 |
| T09 | Revoked certificate | CRL/OCSP says revoked; or stale/unsigned OCSP | M2 |
| T10 | Self-signed in prod context | Leaf == issuer where policy forbids | M3 |
| T11 | Key reuse across identities | One SPKI under multiple subjects | M3 |
| T12 | Issuer anomaly | CA not allow-listed for that subject/domain | M3 |
| T13 | Timestamp forgery | No RFC 3161 token, untrusted TSA, implausible time | M2/M3 |
| T14 | Replay | Payload-digest + signature seen again; sig on new payload | M3 (history) |
| T15 | Verification-failure burst | N invalid sigs from one source in a window | M3 (history) |
| T16 | Key-usage / EKU mismatch | Cert used against its extensions | M2 |
| T17 | Trust-store tampering | Anchor added/removed | M2 (audit + alert) |
| T18 | Quantum exposure | Shor-breakable algo over long-lived / harvestable data | M4 |
| T19 | Anomalous event | ML anomaly score over threshold (advisory) | M5 |

Risk scoring is **noisy-OR** over firing rule weights; ML (T19) blends in at a
configurable weight and can never override a hard crypto failure.

## 5. Residual risk / assumptions

- **Trusted operator.** A malicious admin can add a rogue anchor; it is audited
  and alerted but not prevented.
- **Revocation freshness.** With outbound fetches off, T09 relies on supplied
  CRLs; a cert revoked after its last known-good CRL is not caught.
- **ML scope.** Anomaly detection is advisory and local; an adversary who matches
  the training distribution evades T19 (but not T01–T18).
- **Quantum timeline.** T18 depends on the configurable `qc_year` assumption; the
  score is decision support, not a prediction.
- **Host / container escape, supply chain of pinned deps, and DoS beyond the
  in-process rate limiter are out of scope for v1.**

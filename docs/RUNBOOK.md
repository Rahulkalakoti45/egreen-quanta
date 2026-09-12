# Runbook — Egreen Quanta

Operational procedures for running, deploying and recovering the platform.
Audience: whoever is on the hook when it breaks (likely you, during the demo).

---

## 1. Environments

| | Dev | Production / demo |
|---|---|---|
| Compose file | none (`make dev`) | `docker-compose.prod.yml` |
| DB | SQLite `backend/var/dev.db` | PostgreSQL container |
| Broker/jobs | in-process | Redis + dedicated `worker` container |
| TLS | none (`http://localhost:5173` / `:8000`) | nginx `edge`, ports 80/443 |
| Secrets | dev literals | `.env` (never committed) |

## 2. First-time production bring-up

```bash
cp .env.example .env
# edit .env — at minimum set:
#   SECRET_KEY           (>= 32 random chars;  python -c "import secrets;print(secrets.token_urlsafe(48))")
#   POSTGRES_PASSWORD    (random)
#   REDIS_PASSWORD       (random)
#   ALLOWED_HOSTS        (your hostname, comma-separated)
#   CORS_ORIGINS         (https://your-host)
#   AUDIT_SIGNING_KEY    (optional; base64 Ed25519 seed for signed exports)

# TLS certificate — real cert into deploy/nginx/certs/{fullchain,privkey}.pem, or for a demo box:
sh deploy/nginx/gen-selfsigned.sh your-host

docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps          # all services healthy?
docker compose -f docker-compose.prod.yml logs -f backend
```

The `backend` entrypoint runs `alembic upgrade head` and (if `SEED_ON_START=true`)
seeds demo data. In prod the seeder prints one strong random password **per demo
account, once** — capture it from the logs now or reset it later (§7).

Verify:

```bash
curl -sk https://your-host/healthz                       # {"status":"ok"}
curl -sk https://your-host/api/v1/readyz                  # {"status":"ready","database":"ok"}
```

## 3. Everyday commands

| Task | Command |
|---|---|
| Tail logs | `docker compose -f docker-compose.prod.yml logs -f [service]` |
| Restart the API | `docker compose -f docker-compose.prod.yml restart backend` |
| Apply new migrations | `docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head` |
| Open a DB shell | `docker compose -f docker-compose.prod.yml exec db psql -U egreen egreen` |
| Re-seed demo data | `docker compose -f docker-compose.prod.yml run --rm -e SEED_ON_START=true backend python -m app.seeds.seed` |
| Rebuild after code change | `docker compose -f docker-compose.prod.yml up -d --build backend worker frontend` |

Dev equivalents: `make migrate`, `make seed`, `make dev-backend`, `make dev-frontend`, `make test`, `make lint`.

## 4. Scheduler / background jobs

- The **`worker`** container owns the scheduler (`python -m app.workers.scheduler`).
  Web `backend` containers run with `SCHEDULER_ENABLED=false` so jobs don't run N times.
- Jobs: `audit_anchor` (every `AUDIT_ANCHOR_INTERVAL_HOURS`, default 24) and
  `retention_purge` (every 6 h, only if `RETENTION_DAYS > 0`).
- Check it: `docker compose -f docker-compose.prod.yml logs worker | grep -E "scheduler_started|audit_anchor_written|job_failed"`.
- Force an anchor now: `docker compose -f docker-compose.prod.yml restart worker` — each job runs once ~2 s after the scheduler starts, then on its interval.

## 5. Audit-log integrity

```bash
curl -s -H "Authorization: Bearer $TOK" https://your-host/api/v1/audit/verify
```

- `{"ok": true, "rows": N}` — chain intact.
- `{"ok": false, "broken_seq": K, …}` — row `K` is where the hash chain first
  fails to match. Rows **before** `K` are still trustworthy. Treat as an integrity
  incident: snapshot the DB, pull `worker`/`backend` logs around row `K`'s
  timestamp, and rotate credentials — a mismatch means either DB tampering or a
  bug; both need investigation before you trust new writes.

## 6. Backup & restore

**Backup (run on a schedule):**

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U egreen -Fc egreen > backups/egreen-$(date +%F-%H%M).dump
# also copy: .env (secure store), deploy/nginx/certs/, the modeldata volume if ML is used
docker run --rm -v egreen-quanta-prod_modeldata:/v -v "$PWD/backups":/b alpine \
  tar czf /b/models-$(date +%F).tgz -C /v .
```

**Restore:**

```bash
docker compose -f docker-compose.prod.yml up -d db
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U egreen -d egreen --clean --if-exists < backups/egreen-YYYY-MM-DD-HHMM.dump
docker compose -f docker-compose.prod.yml up -d
curl -s -H "Authorization: Bearer $TOK" https://your-host/api/v1/audit/verify   # confirm chain
```

## 7. Secret rotation

| Secret | Procedure | Impact |
|---|---|---|
| `SECRET_KEY` | set new value in `.env`, `up -d backend worker` | All JWTs invalid → every user logs in again. Refresh tokens in the DB are unaffected (they're random, not signed). |
| Demo/user password | `docker compose ... run --rm backend python -m app.seeds.seed` (dev) or add a small reset via `POST /users` as admin | Just that account |
| `POSTGRES_PASSWORD` | `ALTER USER egreen PASSWORD '…'` in `psql`, update `.env`, `up -d` | Brief backend restart |
| `REDIS_PASSWORD` | update `.env`, `up -d redis backend worker` | Brief broker blip |
| API keys | `DELETE /api-keys/{id}` then `POST /api-keys` | That ingest client re-keys |
| TLS cert | replace files in `deploy/nginx/certs/`, `restart edge` | None if hot-swapped |

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `backend` exits on boot, log says `SECRET_KEY must be set …` | prod fail-closed check | Set a real `SECRET_KEY` (≥ 32 chars) in `.env` |
| 400 `Invalid host header` on every request | `ALLOWED_HOSTS` doesn't include the host you're using | Add it (comma-separated), `up -d backend` |
| Login always 500 | DB not migrated / not reachable | `run --rm backend alembic upgrade head`; check `db` health |
| Frontend loads, API calls fail with CORS error | `CORS_ORIGINS` missing your scheme+host | Fix `.env`, `up -d backend` |
| SSE `/stream/alerts` disconnects every few seconds | a proxy is buffering | Ensure requests go through the `edge` config (it sets `proxy_buffering off` for `/api/v1/stream/`) |
| 413 on a legitimate upload | file over `MAX_UPLOAD_MB + 5` | Raise `MAX_UPLOAD_MB`; also bump nginx `client_max_body_size` |
| `worker` healthy but no anchors | `AUDIT_ANCHOR_ENABLED=false`, or `AUDIT_SIGNING_KEY` unset (anchors still write, just unsigned) | Set the envs; restart `worker` |
| Revocation checks always `not_checked` | `OUTBOUND_REVOCATION=false` (default) | Set `true` **only** if outbound egress is acceptable; private ranges stay blocked |
| ML endpoints 404 / no-op | `ML_ENABLED=false` | Set `true`, restart `backend`, train a model, activate it |
| `pytest` fails only on Windows around `signal` | standalone scheduler signal handlers | expected — `_run_forever` guards `add_signal_handler` with `suppress(NotImplementedError)`; the container runs Linux |

## 9. Load / capacity check

```bash
python scripts/load_test.py --scenario verify -n 500 -c 16 \
  --base-url https://your-host --email admin@egreen.local --password '…'
```

Run it against the Docker stack, not `uvicorn --reload`. Reports RPS and
p50/p90/p95/p99 latency plus a status-code histogram.

## 10. Shutdown / teardown

```bash
docker compose -f docker-compose.prod.yml down            # keep volumes (data safe)
docker compose -f docker-compose.prod.yml down -v         # DESTROY db + redis + models
```

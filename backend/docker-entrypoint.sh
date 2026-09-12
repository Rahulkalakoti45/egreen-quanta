#!/usr/bin/env sh
set -e

echo "[entrypoint] running database migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "[entrypoint] seeding demo data..."
  python -m app.seeds.seed || echo "[entrypoint] seed skipped/failed (non-fatal)"
fi

echo "[entrypoint] starting: $*"
exec "$@"

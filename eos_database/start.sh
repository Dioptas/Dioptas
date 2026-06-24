#!/bin/bash
# Universal entrypoint — works both for local docker-compose and for cloud
# hosts (Render / Railway / Fly.io).
#
# Local compose points DATABASE_URL at the "db" container, which starts at
# the same time and needs a moment to come up — so we wait for it. Cloud
# hosts point DATABASE_URL at Neon, which is already running, so we skip the
# wait (there is no "db" host there — waiting would hang forever, which is
# exactly the "no open ports detected" failure).
set -e

case "${DATABASE_URL:-}" in
  *@db:*)
    echo "Local Postgres detected — waiting for it to be ready..."
    until pg_isready -h db -U eos_user > /dev/null 2>&1; do
      echo "Waiting..."
      sleep 2
    done
    echo "Local PostgreSQL ready."
    ;;
esac

# Ensure tables exist (idempotent). Non-fatal: data already lives in the DB.
python scripts/init_db.py || echo "Warning: init_db did not complete; continuing to serve"

echo "Starting API server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

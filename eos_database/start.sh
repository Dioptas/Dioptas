#!/bin/bash
# Production entrypoint for hosted deployment (Render / Railway / Fly.io).
#
# Unlike wait-for-db.sh (used by local docker-compose), this does NOT wait
# for a local "db" container — the database is Neon, already running and
# reachable via DATABASE_URL. It also binds to the host-provided $PORT and
# runs without --reload.
set -e

# Ensure tables exist (idempotent — create_all is a no-op if they're there).
# Non-fatal: the data already lives in Neon, so a transient init hiccup
# shouldn't take the whole web service down.
python scripts/init_db.py || echo "Warning: init_db did not complete; continuing to serve"

echo "Starting API server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

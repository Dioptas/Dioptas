#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."

# Simple wait loop
until pg_isready -h db -U eos_user > /dev/null 2>&1; do
  echo "Waiting..."
  sleep 2
done

echo "PostgreSQL ready! Initializing database..."

# Initialize database
cd /app
python scripts/init_db.py

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

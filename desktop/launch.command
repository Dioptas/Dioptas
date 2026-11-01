#!/bin/zsh
# Launch Tauri with React/CSS hot reload and the raw CeO2 example.
set -e
cd -- "$(dirname -- "$0")/.."
if [[ ! -x .venv/bin/python || ! -x desktop/node_modules/.bin/tauri ]]; then
  print 'Run uv sync --python 3.13, then cd desktop && npm ci.'
  exit 1
fi
cd desktop
exec npm run tauri:dev -- -- -- --example "$@"

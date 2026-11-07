#!/bin/zsh
# Launch Tauri with React/CSS hot reload and the raw CeO2 example.
set -e
cd -- "$(dirname -- "$0")/.."
if [[ ! -x desktop/node_modules/.bin/tauri ]]; then
  print 'Run cd desktop && npm ci. Rust, a C compiler and CMake are also required.'
  exit 1
fi
cd desktop
exec npm run tauri:dev -- -- -- --example "$@"

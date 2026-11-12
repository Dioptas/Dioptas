#!/bin/zsh
# Launch Tauri with React/CSS hot reload and the raw CeO2 example.
set -e
cd -- "$(dirname -- "$0")"
if [[ ! -x node_modules/.bin/tauri ]]; then
  print 'Run npm ci. Rust, a C compiler and CMake are also required.'
  exit 1
fi
exec npm run tauri:dev -- -- -- --example --backend=rust "$@"

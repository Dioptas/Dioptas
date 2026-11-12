# Dioptas development

The application is Rust/React/Tauri: React UI in `desktop/src`, Tauri host in
`desktop/src-tauri`, native Rust processing in `desktop/backend`. The legacy
Qt/Python app and its test suite live on `legacy/qt`.

Follow `desktop/AGENTS.md`, and read `desktop/README.md` and
`desktop/CALIBRATION_PARITY.md` before changing desktop architecture or workflow.

If an untracked `AGENTS.local.md` exists at the repository root, read it too for
machine-specific notes (checkout locations, worktrees, local files to preserve).

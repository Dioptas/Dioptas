# Python removal audit — November 12, 2026

The legacy Python application, compatibility processor, application packaging,
Qt CI and active Python test/reference suites have been removed from `develop`.
The Qt application and its tests are preserved on `legacy/qt`. The former
React/Python adapter is available in Git history at the pre-cleanup revision
recorded in [../architecture/REFERENCE_DATA.md](../architecture/REFERENCE_DATA.md).

Scientific commands run through Rust/Dioptrin over Tauri-owned stdio. Explicit
Python backend requests fail. Frontend build output is `dist`; native
resources and test input data belong to `resources` and
`tests/data`, rather than a Python package.

Rust tests consume frozen independent numerical outputs, with provenance and
unchanged tolerances. Headless UI and transport checks use the native worker;
a Rust-only fixture generator supplies long series for progress/cancellation
checks. There is no active Python scientific or test-suite dependency.

The two remaining Python source files are documentation configuration
(`docs/source/conf.py`) and the native macOS signing/notarization utility
(`installer/macos/signing.py`). Neither is an application backend or a test suite.
User-authored external actions may still run any explicitly chosen program.

Native format/detector/project support boundaries remain in the individual
parity guides. Removing legacy code does not expand those boundaries or prove
universal scientific equivalence.

# React/Tauri Python-removal audit — 2026-11-07

## Current default

React/Tauri now selects the Rust processor when no backend is specified. This
applies to `tauri:dev`, `launch.command` and embedded Tauri builds. Dioptrin is
the numerical engine. Runtime startup does not look for `.venv`, Python, pyFAI,
FabIO, NumPy or Qt on this path. Explicit `--backend=python` or
`DIOPTAS_BACKEND=python` preserves comparison access; CLI selection wins over
the environment, and invalid selections or missing processors fail explicitly.

The Tauri hooks build and stage `dioptas-processor` for the selected target and
debug/release profile. `bundle.externalBin` copies it beside the host and
includes it when bundling is enabled. This preview still has bundling disabled;
staging a sidecar does not qualify a portable installer. After backend-source
edits, restart Tauri to stage the rebuilt processor. Universal macOS packaging
is explicitly unavailable; individual architecture builds remain possible.

Existing previews are unaffected. These changes are on `codex/native-backend`,
not merged into another checkout or released.

## Command and runtime audit

`npm run test:backend-commands` reads the four Python desktop command registries
as text, without importing Python, and exercises their 102 unique commands
against a Rust child with Python and PATH unavailable. All have native dispatch
routes. Empty-payload acceptance/validation establishes routing only; it does
not prove every argument, numerical result or historical file is supported.

The audit found and fixed `integration_phase_state`: detached phase edits could
not refresh the main window through Rust. It now returns the existing compact
phase/pattern state without replacing detector buffers or changing revision.
A regression test checks this boundary.

The enabled backend normal-dependency tree contains no PyO3, NumPy, pyFAI or
FabIO dependency. The only subprocess facility in native application processing
is explicitly configured external custom actions; users may choose Python for
their own scripts. Such scripts do not make Python an application prerequisite.
The manual geometry form's “pyFAI” label names a coordinate convention.

## Remaining work before deleting the compatibility backend

| Area | Current boundary | Work or explicit scope decision |
| --- | --- | --- |
| Clean builds | The pinned Dioptrin detector commit `5273868599151eb536ddccca56c7fd80437a0754` is local and unpublished. This workspace has it cached. | Publish/merge the shared commit and pin a revision available to CI; no publication was performed by this task. |
| Portable application | The sidecar is staged, but startup still uses a source-checkout root/current directory. The example image also lives in that tree. | Resolve packaged resources independently of build-machine paths; bundle examples, notices and required libraries; test with the source tree and Python absent. |
| Native distribution | Debug macOS builds are checked here. Bundling, signing/notarization, release-profile packaging, Windows/Linux and universal macOS are unqualified. | Build and inspect complete artifacts for each supported platform. No native window was opened for this audit. |
| Historical projects | Native format-2 projects and multiple configurations are supported. Formats 0/1 and legacy transformed-detector projects without an owned physical model fail explicitly. | Implement a qualified importer, retain a separate conversion tool, or document the deliberate compatibility boundary before removing the old reader. |
| Flat-detector options | Ordinary named models, orientations, splines and Fit2D are ported. Arbitrary manufacturer overrides, sensor/parallax settings and NeXus definitions embedding flat/dark corrections are outside the qualified boundary. | Qualify the flat-detector options needed by real projects. Curved detectors are not a missing Dioptas workflow or removal requirement. |
| Reader/selection coverage | Enabled dioptrin-io readers preserve typed data, with explicit scientific rejection of complex/color input and integers outside ±2^53. Standalone JPEG/JPEG2000 and sparse reconstruction are not enabled in this consumer. Generic HDF5 dataset/external-link choices exist as command arguments, without dedicated UI controls. | Decide needed input coverage, add the selection workflow, and qualify representative files against the pinned reader. A broad upstream reader catalogue alone does not prove consumer parity. |
| Phase/project options | Phase/material editing is native. Projects with an enabled DAC thermal-pressure factor other than 0.25 are rejected. | Port required nondefault options or document their boundary. |
| Extensions | All three bundled dynamic masking plugins and LA Cosmic are native. Arbitrary third-party Python plugins are not loaded. | Port needed extensions or define a native extension contract; user-owned external action scripts can remain optional. |
| Qualification and cleanup | Native regression/reference fixtures cover the implemented workflows; they are not universal scientific equivalence proofs. Python still supplies independent test oracles and some old browser test drivers. The Qt application remains Python. | Expand matched checks for actual supported datasets; migrate remaining relevant test drivers; remove the Tauri Python branch/compatibility launcher after accepting the support boundary. Keep independent Python references separate from shipping dependencies. Deleting Qt source or all Python tests is a separate scope decision. |

There is no remaining requirement to run Python in the default React/Tauri
processing path. The remaining decisions concern compatibility, qualification
and distribution. Do not delete the legacy implementation merely because all
command names have routes.

## Verification and reproduction

From `desktop/`:

```sh
npm run backend:test
npm run backend:prepare
cargo test --locked --manifest-path src-tauri/Cargo.toml --no-run
# Execute the reported host-test binary with DIOPTAS_BACKEND unset,
# DIOPTAS_PYTHON=/nonexistent/python and PATH=/nonexistent.
npm run test:backend-commands
npm test
npm run tauri:build -- --debug
npm run test:native-integration
npm run test:native-calibration
npm run test:native-project
```

Checkpoint: 46 native backend tests, 19 host tests and 60 JavaScript tests pass.
The actual Tauri debug build runs the processor-staging hook and produces both
executables without opening a window. Chromium/WebKit checks exercise native
calibration, integration/phases/Batch/Map and project workflows. Command receipts
are in ignored `artifacts/default-backend/`; scientific tolerances remain in the
individual `NATIVE_*_PARITY.md` ledgers.

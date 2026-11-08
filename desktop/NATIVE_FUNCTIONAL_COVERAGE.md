# Native functional coverage and CI

The legacy functional inventory contains **82 source test definitions** in seven
modules. These are definitions, not collected pytest counts: inheritance and
parameterization expand several cases. `functional_coverage.json` records a
case-by-case decision and evidence. The inventory checker runs without Python,
fails on added/renamed/deleted legacy cases or missing native test functions,
and writes a compact receipt under `artifacts/functional-coverage`.

| Classification | Definitions | Meaning |
| --- | ---: | --- |
| Native scientific contract | 58 | A Rust integration test exercises the corresponding supported scientific behavior with actual native commands and data. This does not assert identical Qt widgets. |
| Adapted behavior | 16 | The React/native workflow differs; evidence and the exact remaining difference are explicit in each entry. These are not counted as identical legacy UI parity. |
| Unsupported feature | 4 | Cylinder/sphere corrections, batch rectangle-to-waterfall generation, and standalone detector-image docking are not implemented by the native workspace. Unsupported corrections have atomic rejection tests, not success claims. |
| Platform-specific | 4 | Native Map window management/docking needs isolated OS-level tests. Detached data/progress is tested headlessly; native window semantics are not claimed by this CI. |

## Added native flows

`backend/tests/functional_flows.rs` contains 26 tests, including:

- Raw image → PONI → asymmetric mask → scaled/offset image background → flat
  field → ROI → supersampling → integration with propagated errors, separately
  for 2theta, Q and d. Corrected pixel counts are independently calculated;
  their integrated results are compared with a separately written corrected
  image. Five pattern formats are read back; error columns are independently
  inspected. The project is then reopened and reintegrated by a fresh owner
  after deleting all original detector/calibration/correction files.
- Actual binning/sector/supersampling changes, ROI invalidation and invalid-ROI
  rollback; no mocked integration callback.
- Ordered raw series → inclusive start/stop/stride → f64 processed HDF5 →
  independent dataset readback → stored-only browsing without raw files →
  restored raw inputs and fresh integration with a changed bin count.
- Multiple compressed HDF5 files with an explicit dataset selection: a stride
  crosses the file boundary, preserves frame/path ordering, saves f64 profiles
  and selects/reintegrates the corresponding raw frame from Integration/Map.
- Natural file ordering and corrupt-source rollback; reversible batch
  normalization through a saved/reopened f64 series.
- Image add/average/staged TIFF output, independently decoded original-row
  samples, no source modification and no overwrite of existing staged targets.
- NPY/TIFF-mask/EDF mask round trips, asymmetric coordinates, explicit flips
  and Undo.
- Map integration → independently computed layer algebra → dropped-frame
  blank and grid indices → layer selection → selected raw profile with stable
  Map units → invalid-expression rollback.
- Unit-invariant physical click inspection and independent configuration Map,
  cake and click restoration, including configuration removal.
- Stable incoming-file polling → integration → automatic pattern export;
  changed detector dimensions stop acquisition without publishing stale science.
- Combined correction/background/colored-overlay/phase project persistence;
  phase lattice/name/pressure edits and actual reflection add/edit/remove,
  followed by material export/reload.
- Missing-error export and unsupported corrections preserve existing outputs
  and scientific state rather than silently producing plausible results.

These tests exposed two defects: configuration selection discarded a valid
owned click, and Map reintegration built bins in the global Integration unit
before converting only the axis. The native owner now retains valid per-config
inspection, and reintegrates on the Map's actual unit/grid while preserving the
global Integration preference. The new tests guard both behaviors numerically. The headless gate also exposed
a canvas-focus defect: preventing pointer default left the prior tool button
focused, so Enter could fail to complete a polygon. Accepted plot gestures now
focus their canvas, with an explicit browser assertion before polygon completion.

The [correction and uncertainty ledger](NATIVE_CORRECTION_UNCERTAINTY_PARITY.md)
records the additional transfer/plate/slab, corrected-count variance,
Batch/Map std storage and offline data-flow qualification.

## Gates

`.github/workflows/CI_rust_desktop.yml` runs on relevant pushes, pull requests
and manual dispatch, with read-only repository permissions:

1. **Native processor, Linux and macOS:** formatting, strict Clippy, all native
   processor tests and the real processor build. No Python environment is
   installed by this gate. Linux additionally produces LCOV and HTML coverage
   using cargo-llvm-cov. The local macOS Rust-only baseline is 14,087/19,932
   production-source lines (70.68%, excluding test files and dependencies);
   headless/reference execution is additional and is not included in that
   percentage. The initial report is a baseline, not an invented
   minimum-percentage gate. The opt-in performance benchmark remains ignored.
2. **macOS headless desktop and host:** frontend build/unit tests, the coverage
   inventory, shared control checks, native Chromium/WebKit workflows for
   calibration, masks, integration, projects/configuration/combination, geometry,
   detectors, LA Cosmic, file errors, calibration/image reset and stdio
   cancellation. Tauri host unit tests do not open an application window.
3. **Linux independent references:** a separate CPython 3.13 environment
   supplies pyFAI/NumPy/Qt-model/PhaseSmith/Peritheos reference calculations and
   fixture writers. Thirteen native parity scripts, the remaining bulk/project
   stdio cancellation tests and partial/detached Map progress run here. The
   processor children still have Python and PATH unavailable. The reference
   interpreter is not an application dependency or fallback.

Every gate writes per-step logs; GitHub uploads logs, numerical receipts,
screenshots and coverage reports even when a step fails. A failing scientific
assertion is never converted into a successful skip.

The pinned Dioptrin revision `6ede5d0553811a41ad4511d1f5a50d955eb85156` is now
fetchable on `CPrescher/Dioptrin` branch `codex/rust-desktop-combination`.
All four Git dependency repositories were checked with separate empty Git
object stores; CI does not require the developer's cached local Git objects.
This publishes a dependency development branch, not a new library release.

## Run locally

From `desktop`, after `npm ci` and `npx playwright install chromium webkit`:

```sh
npm run test:ci-native
# Or individual stages:
node scripts/check_native_desktop.mjs --processor
node scripts/check_native_desktop.mjs --ui
node scripts/check_native_desktop.mjs --host
npm run test:functional-coverage
```

The explicit reference stage additionally needs `uv sync --frozen --python 3.13
--extra test` from the repository root:

```sh
# From the repository root; Python is a reference/fixture tool only.
PYTHONPATH=. QT_QPA_PLATFORM=offscreen DIOPTAS_REFERENCE_PYTHON="$PWD/.venv/bin/python" \
  node desktop/scripts/check_native_desktop.mjs --references
```

Coverage can be reproduced with Rust's `llvm-tools-preview` component and
cargo-llvm-cov:

```sh
mkdir -p desktop/artifacts/coverage
cargo llvm-cov --locked --manifest-path desktop/backend/Cargo.toml --all-features \
  --lcov --output-path desktop/artifacts/coverage/lcov.info
```

A supported scientific contract is not universal scientific equivalence: the
real-detector/format qualification boundaries in the other `NATIVE_*_PARITY.md`
ledgers still apply. Successful rejection of a legacy option does not implement
that option, and the four native-window cases remain explicitly outside this
headless gate.

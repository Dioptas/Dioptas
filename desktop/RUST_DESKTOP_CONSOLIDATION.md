# Rust desktop consolidation — November 8, 2026

The primary desktop development branch is `codex/rust-desktop`, checked out at
`/Users/clemens/ChatGPT/Dioptas Rust Desktop/worktrees/rust-desktop`.
The workspace's `Dioptas` symlink and launcher select it. New scientific desktop
features belong in `desktop/backend`; Rust/Dioptrin is the default processor and
the workspace launcher explicitly selects Rust. No scientific HTTP server runs.

## Included work

| Source | Preserved checkpoint | Integration |
| --- | --- | --- |
| Native migration | `abb4a579`, local snapshot `fe029512` | Base; calibration, detector geometry, masks/plugins, LA Cosmic, processing, phases/overlays, Integration, Batch/Map, projects and standalone packaging |
| Scientific UI audit | `88b52c09` | Merge `86bdbf4f`; readable controls, keyboard/focus behavior, draft guards, error reporting, plots and layout |
| Detector combination | `6db5c58d` | Merge `37b7dfdf`; shared UI components and combination controls; processing ported to native Rust |
| Latest primary desktop | `f5ad5732`, local snapshot `33c9f0e8` | Merge `abe9a178`; navigation modifiers, display options and calibration-change workflow |
| Linked Map navigation | `72b9e62c` | Merge `3fc0a8ba`; reconciled with shared detector/pattern views and persistent zoom preferences |

Existing source checkouts and uncommitted files were preserved. Isolated-index
snapshots, patches and a manifest are in the workspace's
`archives/consolidation-2026-11-08/`. A final comparison found no additional
source changes after those snapshots. Snapshot refs retain the original Git
history. No Qt release branches were merged into or rewritten by this task.

The experimental single-crystal/CrysAlis work stays on `codex/desktop-scxrd`
(`dd9795d3`, dirty snapshot `5cb1634b`) in `worktrees/scxrd`, as requested. Its
Python-dependent experimental commands are not exposed by the default Rust app.
Phase/overlay grouping remains a separate design discussion.

## Reconciled behavior

- Source-size changes, including variable-size TIFF frames and next-file
  navigation, request a decision before publishing pixels or reusing geometry.
  Cancel/Escape preserve the session. Accept resets detector geometry,
  transformations, masks/plugins, corrections/image backgrounds, picks, detector edit
  history and derived integration results while keeping the current workspace and tab.
  Phase and overlay references remain available. An unreadable accepted image
  rolls back the reset. Autoprocess stops safely on a size change.
- Reset calibration uses the same native reset while retaining the current
  original-orientation image. Same-size replacements retain calibration.
  A different physical detector with the same dimensions still requires the
  explicit reset. Supported manufacturer binning can resolve the first image;
  subsequent size changes prompt.
- Configuration controls remain opt-in under Settings → General. Integration
  adds detector factors, combined patterns/cakes and explicit combined-pattern
  export, with one configuration selector. Independent detector and
  individual/combined-cake display settings use stable configuration identities.
  Configuration changes are disabled while scientific drafts need applying or
  discarding.
- Combination accumulates native shared-grid contributions before normalizing;
  it does not average independently normalized curves. Separate warm pattern
  and cake plans retain detector geometry, masks, units and correction settings.
  Combination flags and factors survive native project round trips.
- Shared UI primitives own controls, dialogs and fields across all views.
  The audited typography, disabled-state readability, draft handling, keyboard
  navigation and dialog focus restoration remain. Native mask Undo/Redo routes
  to mask history; Calibration/Integration use their shared scientific history.
  Both toolbar and keyboard shortcuts follow that boundary.

Combination requires solid-angle correction. Combined counting errors now
propagate through detector factors, backgrounds and supported corrections; see
the [correction/uncertainty ledger](NATIVE_CORRECTION_UNCERTAINTY_PARITY.md). The qualified native detector/project/reader limits remain in
`NATIVE_*_PARITY.md` and `PYTHON_REMOVAL_AUDIT.md`; this consolidation is not a
claim of universal Qt equivalence. Compatibility Python source and independent
reference tests remain outside the shipping runtime. A few transport/Map tests
use `DIOPTAS_REFERENCE_PYTHON` only to generate reference fixtures; their Rust
children run with Python and PATH unavailable.

## Released dependency and portability

The desktop uses the public Dioptrin **0.12.0** release as its baseline.
The current exact pin in `backend/Cargo.lock` is `7f2d0c2`, which adds the
Massif preprocessing optimization, prepared compatibility integration plans
and resident CSC/CSR selection
on top of `v0.12.0`. These additions are not part of the published 0.12.0 package;
see [Massif performance](MASSIF_PERFORMANCE.md) and
[cached integration performance](PYFAI_CACHED_PERFORMANCE.md).
CSR is the default. Optional Automatic uses CSC above roughly 8 MP and 2,000 bins without Poisson errors. The execution-layout setting and empirical
predictor are documented in the [crossover study](INTEGRATION_LAYOUT_CROSSOVER.md).
The release includes physical detector geometry, shared-grid integration,
explicit count variances, and the `PyfaiFull` integration method used for
both 1D patterns and 2D cakes. Fractional polygon splitting remains the default.

This release publishes the previous desktop-specific geometry and integration
work. A clean checkout can resolve the current dependency from GitHub without this machine's Cargo
cache or a local library checkout. The bundled application owns its compiled
processor and resources. Python remains an independent reference or explicit
compatibility runtime; the default desktop processing runs in Rust.

## Verification

- Frontend build and 75 unit/architecture tests pass.
- Native processor: 71 tests pass; one opt-in performance benchmark is ignored.
- Tauri host: 21 tests pass. Native Clippy passes with warnings denied.
- Shared controls: headless Chromium and WebKit, normal and larger text.
- Image-change/reset: both browsers, Cancel/Escape/focus return, compact layout,
  same-size reuse, accepted reset, and native variable-size frame regression.
- Calibration and dynamic mask/plugin workflows: both browsers, including
  grouped edits, native fit/live previews, imprint and Undo/Redo.
- Projects/configurations/combination: both browsers, add/duplicate/rename/
  select/remove, hidden-by-default preference, compact controls, factor,
  combined results/export and project reopen.
- Native Integration/Batch/Map, file-error dialogs and partial Map progress:
  both browsers. Seven stdio progress/cancellation/source-mutation tests pass.
- A local macOS arm64 debug `.app` was rebuilt, ad-hoc signed and inspected:
  701 resource checksums, 343 Cargo and five JavaScript notice records, no
  Python source/runtime or external runtime library dependencies.
- A relocated packaged processor passes integration, combined results/export
  and project round trip in a headless sandbox denying the source checkout,
  with Python/PATH unavailable. No visible application windows were opened;
  existing previews and processing were not terminated.

The artifact is `desktop/src-tauri/target/debug/bundle/macos/Dioptas Desktop.app`.
This is a local development build, not a notarized or published release.
Headless receipts/screenshots are under `desktop/artifacts/`.

## Subsequent CI qualification

The native functional coverage stage publishes the pinned dependency development
branch, adds an automatic Rust/headless/reference CI gate and 19 additional Rust
flow tests. See `NATIVE_FUNCTIONAL_COVERAGE.md`. The local-only dependency
limitation above describes the original consolidation, before that stage.

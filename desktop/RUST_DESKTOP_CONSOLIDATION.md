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
The current exact pin in `backend/Cargo.lock` is `41174d8`, which includes the
Massif preprocessing optimization, prepared compatibility integration plans
resident CSC/CSR selection and reusable native dynamic CSC workers with
supplied pixel variances
on top of `v0.12.0`. These additions are not part of the published 0.12.0 package;
see [Massif performance](MASSIF_PERFORMANCE.md) and
[cached integration performance](PYFAI_CACHED_PERFORMANCE.md).
Corrected and dynamically masked series are qualified in the
[processed-series pipeline](NATIVE_PROCESSED_SERIES_PIPELINE.md).
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

## Cake Q-axis and azimuthal-profile integration — November 10, 2026

This integration combines `6ee8faf0` (cake Q display) and `b82067d4` (native
azimuthal profiles), preserving both view hooks and native requested products.
Cake metadata remains scientific source coordinates; rounded display ticks
invert the nonlinear conversion without rebinning. Profile extraction continues
using the owned float64 grid. Combined source units survive project reopen.
Joint tests cover unchanged profile samples, buffers, physical selection and
both viewports across angular/Q displays and d pattern selection.

The merged tree passes 209 native tests (two existing ignored checks), 110
frontend tests, 27 Tauri host tests, native Clippy and frontend build. Headless
Chromium/WebKit pass both feature workflows, compact Standard/Larger layouts,
real-image calibration and Integration. The global host rustfmt check reports
pre-existing differences in unrelated modules; they were left intact. No user
preview was closed or processing terminated. No package/release was published.
See [cake-axis qualification](CAKE_Q_AXIS_PARITY.md) and
[profile qualification](CAKE_PROFILE_PARITY.md); receipts and screenshots live
under the ignored `desktop/artifacts/cake-q-axis/` and `cake-profile/` folders.

## Detector window and correction-preview integration — November 10, 2026

This merge brings `62473343` (native correction Plot/Back previews) and
`3fbf2686` (standalone detector image) into the consolidated checkout after
`53fe41b2`. The cake Q-axis and azimuthal-profile implementations remain intact,
including their source-coordinate conventions, requested products and controls.
The image Save action uses the detached renderer while Profile remains available.
Profile reads and exports are included in the correction preview's read-only
command set so they cannot dismiss an open correction map.

The joint headless source workflow selects Q, enables an azimuthal profile,
opens a detached correction map and changes profile width. It checks that the
map stays open, native profile extraction occurs, scientific state and pixel
identities stay unchanged, and no second correction-preview calculation runs.
Both Chromium and WebKit pass this workflow and the separate detector,
correction-preview, cake Q-axis, cake-profile, measured-image calibration,
Integration/Batch/Map and responsive-control regressions.

Verification on the merged tree:

- Full native processor suite: **212 passed, two existing opt-in tests ignored**.
- Frontend: **112 passing tests**, production build and functional inventory.
- Tauri host: **29 passing tests**; strict backend and host Clippy pass.
- Isolated macOS native detector campaign: binary/cached snapshots, restricted
  child commands, single-window reuse, dock/close, placement restoration and
  main-frontend reload reconnection pass; one processing PID is retained and
  the test's processor is reaped on final exit.

`test:ui-components` still fails the previously reproduced baseline **Phase
parameters scrollbar gutter** assertion (12 px expected, 0 observed). This
integration leaves that unrelated implementation and fixture unchanged.
Windows/Linux native window behavior remains unqualified. No package or release
was published. Receipts and screenshots are under the ignored
`desktop/artifacts/detector-window/`, `correction-previews/`, `cake-profile/`,
`cake-q-axis/`, `native-calibration/`, and Integration test artifact folders.


## Spottiness integration — November 10, 2026

`132061d9` integrates the native Spottiness controls, linked population std or
std/mean diagnostic and atomic single-pattern CSV export. Reconciliation retains
the generic azimuthal profile plot, source-preserving cake unit changes, shared
clicks, detector-window controls and correction previews. Relative display
switches reuse the same native samples; Spottiness exports preserve an open
correction map on success, cancellation or failure. Background subtraction and
clipping do not alter the original mean/std observables. A descending d-spacing
background path now reverses std along with the other radial arrays.

Primary checks pass: frontend build and 112 tests; 86 relevant native tests
(two existing opt-in checks ignored); strict backend Clippy/formatting; the
Tauri CSV dialog contract; seven independent scientific reference cases; and
headless Chromium/WebKit Spottiness, cake-profile, cake-Q, detached-detector and
correction-preview workflows. No visible test windows were opened, existing
previews were preserved, and no package/release was published. See
[Spottiness qualification](SPOTTINESS_PARITY.md) for statistics, coverage and
remaining combined-pattern/splitting limitations.

## Shared-controls scrollbar fixture correction

The previously reported Phase parameters gutter failure came from a stale test
fixture: `.phase-step-controls` is a two-field menu grid, not a scroll container.
The fixture now exercises the editor's `.pe-parameter-scroll` container and
explicitly checks computed overflow behavior before measuring scrollbar space.
The existing 12 px gutter and idle-visibility assertions remain unchanged.

`npm run test:ui-components` passes in headless Chromium and WebKit at Standard
and Larger text sizes, including vertical, horizontal, nested and non-overflow
cases. All 112 frontend tests and the production build pass. Application layout
and scrollbar styles are unchanged; the earlier fixture failure is resolved.
Receipts and screenshots are in `desktop/artifacts/ui-components/`.

## Complete detached image workspace (main Tauri checkout)

The Integration Undock action now sits at the lower right of the image toolbar,
with the other controls aligned left. All image controls and the optional
azimuthal profile move into the companion; image/cake switching retains independent display state. Removing
the main image pane gives its space to the pattern, and docking restores the
saved split. Docked Batch now fills the freed image column; if both views are
detached, the task tabs and pattern use the full main-window width. Figure-editor, phase-controls and Spottiness changes
already in this checkout are preserved.

The follow-up also fixes a compact profile rendering loop caused by tick density
depending on its own annotation margin. The same main Rust command queue owns
ROI, display settings, profile extraction/export and image saving.

Validation: production build, 112 frontend tests, and headless Chromium/WebKit
shared controls (both text sizes), detached detector/source, correction previews,
cake profile/Q, Integration responsive layout and Integration panel workflows.
Tests cover 420/520 px complete detached toolbars, lower-right placement, freed
pattern width and restored split, image/cake contrast separation, profile export,
and an unchanged live Batch heatmap across image detaching/docking. See
[detector-window evidence](DETECTOR_WINDOW_PARITY.md). No visible native window
was opened for this UI follow-up.

## Batch fills the detached image's space

The docked Batch now fills the freed image column at wide and compact sizes,
instead of retaining its fixed inline height. Its image/Batch divider and
Collapse action are temporarily removed while filling. Re-docking the image
restores the user's saved Batch height and collapse preference. Detaching Batch
as well leaves only full-width task tabs and pattern; re-docking Batch restores
the expanded series without bringing the detector back.

Verified with headless Chromium/WebKit Integration responsive and panel workflows,
113 frontend tests and the production build. Bounds assertions cover the full
Batch pane and heatmap area, both floating views, re-docking, renderer retention,
and restoration of resized/collapsed preferences. See [Batch parity](BATCH_PARITY.md).

## Shared docking icon (2026-11-11)

Detector, Batch and Map now share a 16 px `DockWindowIcon`: the existing
ExternalLink window outline with its diagonal arrow pointing back inside.
Main-window and companion Dock actions use the same component; Batch's Detach
icon also uses the matching 16 px size.

Production build, 113 frontend tests and headless Chromium/WebKit Integration
responsive checks pass. Focused native-processor Map detach/dock checks pass in
both browsers, including the shared icon and button size. A 16/32 px rendered
icon comparison is in `artifacts/window-icons/`. The broader legacy
`map_window.mjs` check timed out at its frame-selection/title assertion before
reaching docking; that workflow was not changed for this icon update.

## Map frame-selection check correction (2026-11-11)

The legacy Map companion timeout recorded above is resolved by using rendered
plot/viewport coordinates and waiting for the companion's controls and fitted
layout before clicking. The strengthened fixture verifies forwarded cell
coordinates, backend frame/cell state, title, clean integration and regenerated
cake. Its rapid-selection test uses a controlled gate and checks command order.

`npm run test:map-window` passes in headless Chromium and WebKit against the
existing explicit Python reference bridge, including selection after resizing,
export, display preferences and dock/close/reopen. Production build passes.
Receipts and screenshots are preserved separately under
`desktop/artifacts/map-window/chromium/` and `webkit/`. No application scientific
or native window-management code changed.

## Rust-backed Map window checks (2026-11-11)

Added `npm run test:map-window-native` using the real native stdio processor
with Python fallback disabled. Headless Chromium and WebKit pass frame/cell/title
selection after resizing, deterministic queued clicks, visible cake regeneration,
layer edits, PNG export, display-state retention, compact Larger text and
dock/close/reopen. The fixture displays Cake before asserting regeneration,
respecting the native policy of skipping hidden cakes, and verifies a new cake
buffer after native selection.

The current Rust processor build and both Python reference browser runs also
pass. Runtime/browser-specific receipts record the Rust processor PID and ordered
cell requests under `desktop/artifacts/map-window/rust/{chromium,webkit}/`;
reference evidence is kept separately under `python-reference/`. Only the test
harness and commands changed; no scientific implementation or native OS window
management changed. See [Map parity](MAP_PARITY.md).

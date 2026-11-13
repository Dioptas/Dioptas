# Rust desktop consolidation — November 8, 2026

The primary desktop development branch is `develop` (promoted from
`codex/rust-desktop` on November 11, 2026), checked out at
`/Users/clemens/ChatGPT/Dioptas Rust Desktop/worktrees/rust-desktop`.
The workspace's `Dioptas` symlink and launcher select it. New scientific desktop
features belong in `backend`; Rust/Dioptrin is the default processor and
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
the [correction/uncertainty ledger](../parity/NATIVE_CORRECTION_UNCERTAINTY_PARITY.md). The qualified native detector/project/reader limits remain in
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
see [Massif performance](../performance/MASSIF_PERFORMANCE.md) and
[cached integration performance](../performance/PYFAI_CACHED_PERFORMANCE.md).
Corrected and dynamically masked series are qualified in the
[processed-series pipeline](../performance/NATIVE_PROCESSED_SERIES_PIPELINE.md).
CSR is the default. Optional Automatic uses CSC above roughly 8 MP and 2,000 bins without Poisson errors. The execution-layout setting and empirical
predictor are documented in the [crossover study](../performance/INTEGRATION_LAYOUT_CROSSOVER.md).
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

The artifact is `src-tauri/target/debug/bundle/macos/Dioptas Desktop.app`.
This is a local development build, not a notarized or published release.
Headless receipts/screenshots are under `artifacts/`.

## Subsequent CI qualification

The native functional coverage stage publishes the pinned dependency development
branch, adds an automatic Rust/headless/reference CI gate and 19 additional Rust
flow tests. See `../parity/NATIVE_FUNCTIONAL_COVERAGE.md`. The local-only dependency
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
See [cake-axis qualification](../parity/CAKE_Q_AXIS_PARITY.md) and
[profile qualification](../parity/CAKE_PROFILE_PARITY.md); receipts and screenshots live
under the ignored `artifacts/cake-q-axis/` and `cake-profile/` folders.

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
`artifacts/detector-window/`, `correction-previews/`, `cake-profile/`,
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
[Spottiness qualification](../parity/SPOTTINESS_PARITY.md) for statistics, coverage and
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
Receipts and screenshots are in `artifacts/ui-components/`.

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
[detector-window evidence](../parity/DETECTOR_WINDOW_PARITY.md). No visible native window
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
and restoration of resized/collapsed preferences. See [Batch parity](../parity/BATCH_PARITY.md).

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

`npm run test:map-window` passes in headless Chromium and WebKit against Rust,
including selection after resizing,
export, display preferences and dock/close/reopen. Production build passes.
Receipts and screenshots are preserved separately under
`artifacts/map-window/rust/chromium/` and `webkit/`. No application scientific
or native window-management code changed.

## Rust-only Map window checks (2026-11-11)

`npm run test:map-window` now runs the real native stdio processor by default.
The harness's Python runner and reference mode have been removed.
`npm run test:map-window-native` remains an alias for the default command.

Headless Chromium and WebKit pass frame/cell/title selection after resizing,
deterministic queued clicks, visible cake regeneration, layer edits, PNG export,
display-state retention, compact Larger text and dock/close/reopen. The fixture
displays Cake before asserting regeneration, respecting the native policy of
skipping hidden cakes, and verifies a new cake buffer after selection.

The Rust processor build passes. Receipts record the runtime, processor PID
and ordered cell requests under
`artifacts/map-window/rust/{chromium,webkit}/`. Only the test harness and
commands changed; no scientific implementation or native OS window management
changed. See [Map parity](../parity/MAP_PARITY.md).

## Rust-only detector and Batch companion checks (2026-11-11)

Audited and reran `test:detector-window`: its worker and fixture generation use
Rust, with no Python bridge. The source check now explicitly asserts the runtime.
Migrated the older Batch companion test to the Rust processor and a Rust example
that generates the six scaled real detector TIFFs. `test:batch-window` runs
Chromium and WebKit; its fixture/file chooser remains test-only, and the native
client disables Python/PATH fallback. Separate visible detector/Batch smoke and
layout scripts explicitly request `--backend=rust`.

Both headless detector and full Batch companion/dock workflows pass, along with
the production build and 113 frontend tests. Batch assertions now use native
inclusive normalization bins and current compact-layout scrolling/tab behavior.
Evidence is under `artifacts/detector-window/` and
`artifacts/batch-window/rust/{chromium,webkit}/`.

Detached detector/cake/profile live mouse coordinates are no longer duplicated
in the main footer. The last-click position remains visible in both windows for
comparison with live mouse positions. The main pattern retains its readout, and
docking restores live detector readouts in the main footer. Regression checks
cover matching click fields in both windows and these transitions. Scientific processing and linked inspection are unchanged.
Visible OS-window campaigns were not rerun for this headless follow-up.

The detached detector check now explicitly verifies image → pattern → image
clicks, matching footer fields, the main pattern marker and the projected image
point/contour against the shared Rust selection. Both Chromium and WebKit pass;
application behavior already supported both directions, so only regression
coverage and evidence were added.

Extended the Rust-backed detached detector workflow to verify cake ↔ pattern
clicks in 2θ and Q display modes. It checks matching click fields in both
windows, both linked markers, the cake click-point projection and preserved
azimuth after pattern clicks. Headless Chromium and WebKit pass; only regression
coverage and evidence changed.

The detached Batch companion now retains the shared click-position readout in
its footer, separately from live mouse values. Regression checks exercise Batch
→ pattern → Batch clicks and verify both markers and matching footer values.
Pattern clicks must keep the Batch's selected frame and intensity matrix intact.
Only the changing click metadata is forwarded to the companion. Both headless
Rust-backed Batch browser workflows, the build and 113 frontend tests pass.

The Map companion now shares the retained radial click readout. Pattern clicks
update it in the child; scan-cell clicks load the selected pattern while keeping
that physical radial bookmark. Regression coverage verifies both directions,
matching footer fields, selected-cell publication, changed scan patterns and
retention of the map grid/frame on pattern-only clicks. Rust-backed Chromium and
WebKit workflows, the production build and all 113 frontend tests pass.

## Simultaneous detector, Batch and Map companions (2026-11-11)

Added `npm run test:companion-windows`: one Rust owner with all three companions
and the main pattern open together. Headless Chromium and WebKit pass ten click
transitions each, covering image, pattern, Batch, Map, Cake and Q units. Each
step verifies four matching retained-click readouts and linked markers, keeps
Batch/Map frame selections independent and preserves the radial bookmark when
switching Map cells. The companions remain open and reuse one processor per
browser run. Evidence is in `artifacts/companion-windows/`.
Only regression coverage and its command/documentation were added.

## Dock/re-detach click synchronization regression (2026-11-11)

Extended the joint companion test to 42 checks in each browser. Detector, Batch
and Map each dock and detach twice, retaining the physical click bookmark while
the other companions remain open. New clicks from the main pattern, docked
plots and recreated companions must propagate; Map cell changes must retain
the bookmark. Both 2θ/Image and Q/Cake workflows are covered, including Map's
separate image surface and stored-pattern units. The test is now part of the
default native UI gate as well as `npm run test:companion-windows`.

## Promotion to develop — November 11, 2026

The former Qt `origin/develop` tip
`253d0fda505d4f9b159644050efe2f574ce8a3d9` is preserved unchanged on
`legacy/qt`. The promotion joins the divergent histories while retaining the
Rust desktop implementation tree; it does not reapply Qt release changes to
the native application. Both histories remain reachable without rewriting
`develop`. Existing release tags and `main` are preserved.

The primary worktree and workspace symlink stay in place, now on `develop`.
`codex/rust-desktop` remains a compatibility branch. The single-crystal
experiment and other feature worktrees remain separate.

Root documentation directs new development to Rust/React/Tauri and released Qt
users to the legacy guide. Qt CI and automatic branch packaging target the Qt
branches; the native desktop workflow continues to own Rust qualification.
The inherited Qt tag workflow verifies that a tag is on the legacy Qt line
before building or publishing. This promotion does not publish a release.

The previously uncommitted native changes were reviewed and committed before
promotion: `212ad25c` (mean-signal waterfall spacing), `c8817442` (phase ordering,
compact controls and clear confirmation) and `8e3111f6` (responsive Integration
groups and Overlay toolbars). A pre-existing Clippy test-module placement issue
was fixed without changing phase calculations. The original 18 files were
verified byte-for-byte before committing.

Promotion validation: 117 frontend tests, frontend production build, 269 Rust
tests (two existing ignored checks), native formatting and Clippy with warnings
denied. Rust-backed headless Chromium/WebKit checks pass Integration responsive
workflows, 48 Phase-height layouts, 304 Overlay-width samples and full Batch
companion/dock workflows. Workflow syntax and expressions pass actionlint. These
checks do not qualify a new cross-platform binary release.

## Review corrections and command foundations — November 11, 2026

The full-code-review follow-up fixes the nine recorded findings and adds
regressions at the affected command, project, transport and UI boundaries:

- Oversized export requests fail before the host writes to stdio. Direct-client
  oversized frames are bounded, drained and rejected while retaining the session.
- Project serialization clears removed flat-field references. Background edits
  and project loading share one typed validator, including the supported upper
  iteration/order limits and legacy project values.
- Single-pattern and automatic d-axis FXYE exports use physical angular
  coordinates, with the same export-unit selection as Batch. Live pattern units,
  samples and counting errors retain their scientific ownership.
- Queued overlay edits target stable UIDs, including Undo grouping. Deleted
  identities cannot redirect later edits to a different row.
- One shared host/processor command policy owns cancellation classification,
  including transfer corrections and delegated image/frame/source loading.
- Incoming files that fail while being written are retried after their own
  size/modification time changes and becomes stable again. Unchanged corrupt
  files do not block later arrivals. This is a top-level-file watcher; it does
  not watch changes confined to an HDF5 master's external children.
- Series construction, metadata and append use a shared immutable file index,
  retaining first-row, sparse-frame-count and source-order semantics with linear
  indexing work.
- Waterfall checks cover both intended layouts and the mean-based spacing
  heuristic. Project checks distinguish cake source/display units and require
  the scientific cake buffer to survive unit-only changes.

After the complete fixes-only local gate passed, the first frontend architecture
increment extracted ordered command scheduling from `App.tsx` into a pure
coordinator. Its explicit outcomes and reservation cleanup have adversarial unit
coverage. Response application and the existing controls remain owned by the
React application. The following increment extracts response ownership and adds
typed contracts; see [the command contract](../architecture/COMMAND_CONTRACT.md) for the current
boundaries.

The fixes-only gate passed 283 Rust tests (two existing opt-in checks ignored),
117 frontend tests, all native headless workflows, 18 independent numerical
reference groups and 37 Tauri host tests. The coordinator adds six frontend
tests and is validated separately across the headless UI gate. Local receipts
are under `artifacts/review-fixes/`; no visible native windows are needed
for these checks.

Clean CI dependency resolution also replaces the unreachable PhaseSmith source
pin with the public 0.8.1 revision. All source files in its six linked crates
retain identical Git blob identities; the changes are package manifests. Current
pins and the source-identity audit are documented in
[native integration qualification](../parity/NATIVE_INTEGRATION_PARITY.md).


## Typed commands and response ownership — November 11, 2026

The frontend command registry now covers 122 native/host-mediated commands,
including command-specific payloads, results and deferred/cancelled outcomes.
Direct calls and generic forwarding preserve the command/payload relationship
and reject extra payload fields. Compile fixtures cover positive calls, invalid
names/fields/types, required operation data, dynamic command correlation, nullable
native results and success-only result narrowing. Batch/Map controls retain their
callback-free API; detached edits promise only acknowledgements, with scientific
data published through their existing snapshots.

A canonical structural schema generates shared TypeScript and borrowed Rust DTOs
for the first 15 native command families. Generated-file checks run in each gate
and the frontend build. Native validation checks covered present fields at the
Tauri chooser/request boundary and processor request boundary. Existing handlers
retain scientific ranges, defaults, required fields and legacy operations. This
is incremental native DTO coverage; the remaining Rust scientific handlers retain
their existing validation. Common response factories preserve the existing
success/error/cancellation/decision metadata and binary framing.

`App.tsx` now composes a pure response snapshot transition, its React owner, a
workspace effect adapter and a command response transaction. Canonical backend
state remains separate from the rendered pattern-only merge. Deferred decisions,
stored-map fallback, linked-position/Auto-level preparation, publication,
completion effects and recovery retain their existing ordering inside the command
reservation. Regression tests preserve omitted/null behavior, exact raster-buffer
owners, calibration/geometry/ROI identities, source/configuration changes and
callback/error cleanup. No scientific algorithm or interface layout is changed.

Local qualification passes all processor, UI, numerical-reference and host gates:
290 Rust tests (two existing opt-in checks ignored), 44 Tauri host tests, 154
frontend unit tests, four compile-fixture files, generated-contract drift checks,
strict Clippy/formatting and the production build. The complete headless gate
passes, including Chromium/WebKit response ordering, retained plot products,
project/configuration changes, HDF5 sources, companion windows and transport
cancellation. All 18 independent numerical-reference groups and their fixture
transport/Map-progress checks pass. Separate Chromium/WebKit correction-preview
and cake-profile workflows also pass. Local receipts are under
`artifacts/typed-response-refactor/`; no visible application windows are
used for this qualification.

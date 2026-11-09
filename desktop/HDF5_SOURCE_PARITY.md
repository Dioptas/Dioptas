# Native HDF5 image-source selection

The Calibration Image section and Integration Image tab offer Qt's compact
**Image source** dropdown when HDF5 image sources are available. Options show
the master-file dataset path, frame count and detector dimensions. There is no
general HDF5 tree/data browser. The Qt reference is
`ImageController.update_img_control_widget`/`select_source`, `ImgModel.load_hdf5`/`select_source`
and `hdf5Loader.find_image_sources`.

Generic HDF5 files initially open the first supported source in sorted path
order. Unlike Qt's rank ≥ 3 discovery, native admission supports scalar 2D planes
and 3D frame stacks; unsupported component/complex arrays, filters, storage and
reader limits retain their native rejection. Metadata admission does not promise
that all pixel values will decode: e.g., integers outside ±2^53 still fail
explicitly when selected. No failed selection substitutes another dataset.

Recognized Eiger/LImA/Lambda conventions keep their established automatic load,
including concatenated Eiger parts. **Automatic beamline series** remains a
separate option after selecting an individual dataset. An explicit dataset is
stored in the image's reader options; automatic selection leaves `dataset`
absent. Dataset paths retain the master's link aliases rather than silently
replacing them with a resolved file's path.

`select_image_source` retains the current zero-based frame, clamped to the last
frame of a shorter source, matching Qt. `state.integration.frame` and the UI's
frame field use positions starting at 1, matching `integration_navigation.frame`;
`open_image.frame` and `nativeSource.frame` remain zero-based. Selection passes through the ordinary transactional image load:
source-size changes ask for Cancel or Open and reset calibration; acceptance
retains the current workspace and tab, while same-size changes retain geometry
and transformations. Image/mask/processing and pattern,
cake and combined results use that same boundary. Cancel, Escape, decode/read
failure and native cancellation retain the previous session. Source selection,
catalog and frame belong to each configuration; native format-2 project caches
retain them even when original files are offline. Navigation reopens the
selected dataset and fails if it is unavailable, preserving cached pixels.

Integration → Image includes Qt-style previous/next frame arrows and an
independent Frame step alongside direct frame entry. Relative requests resolve
against the worker's current frame, so queued clicks accumulate. Overshooting
clamps to the first/last frame of the selected source and never opens a neighboring
file; the corresponding boundary arrow is disabled. The controls appear only
for multi-frame images and also use the same native path for non-HDF5 stacks.
The separate file arrows always browse files, using their own File step and
By Name/By Time setting, and open the destination's first frame. They retain the
selected HDF5 source and never substitute a frame when a neighboring file is missing.

Discovery uses the pinned native NeXus immutable metadata snapshot for exact
soft/external-link resolution and typed readers for dataset admission. Metadata
enumeration visits only concrete paths from that validated graph; it does not
invoke HDF5 external-file search or decode scientific pixels. Group cycles and
alias expansion are bounded. External links retain the existing explicit
`follow_external_links: true` command/project setting, including after source
switches and navigation; the dropdown never enables that policy implicitly.
There is no new external-link consent/relocation UI. Recognized automatic or
explicitly named sources can still load when unrelated metadata prevents a full
catalog; the source control displays that discovery error instead of hiding it.
Existing native reader limits, VDS/raw-storage admission and immutable-file
requirements still apply. This is scoped qualification, not coverage of every
HDF5 producer or unsupported native reader format.

## Verification

`cargo test --locked --manifest-path backend/Cargo.toml --test hdf5_sources`
uses Rust-generated real HDF5 files to cover:

- Multiple datasets with four/two/three frames, different detector shapes,
  2D planes and exclusion of unsupported ranks; original pixel values and
  frame/file navigation.
- Same-size source changes retaining geometry, expected proportional integrated
  intensities and updated cake buffers; shorter-series frame clamping.
- Read-only size prompts, accepted resets, explicit missing datasets, U64
  precision failures before/after reset, cancellation and exact session rollback.
- Independent configurations, owned project caches, offline reopen and recovery
  to selected-source navigation when files return.
- Automatic concatenated Eiger series, explicit dataset and automatic switches,
  external dataset/group links and soft aliases, default link rejection and
  explicit FollowSnapshot admission.

`npm run test:hdf5-sources` uses that same Rust processor (Python/PATH unavailable)
and Rust-generated HDF5 fixtures through headless Chromium and WebKit. It covers
both source selectors, frame-field navigation, compact layout at both text sizes,
Cancel/Escape/focus restoration, the existing file-error dialog, project
save/reopen and accepted source-size reset. Screenshots and a receipt are under
`artifacts/hdf5-sources/`. This check is included in `test:ci-native`.
It also exercises frame arrows/steps, end clamping, rapid queued clicks, invalid
step recovery, and independent file/frame steps retained across Integration tabs.
The Rust source tests check relative stepping with neighboring files present,
selected-source retention, pixel/pattern/cake updates, and invalid-request rollback.

Validation on November 8, 2026: all 128 Rust tests passed (one optional
performance benchmark ignored), Clippy passed with warnings denied, all 75
frontend unit/architecture tests passed, and the frontend production build
passed. Source-selection and existing image-change/reset browser suites passed
in both headless Chromium and WebKit. No visible test windows were opened.

## Primary-checkout integration — November 9, 2026

The feature is integrated with the primary checkout's newer Dioptrin runtime,
requested-product pipeline and native history transfer. Project metadata retains
both source-selection fields and the existing integration method/sparse-layout
fields. The current reset workflow retains its workspace and tab. A seventh
native HDF5 regression verifies source changes with hidden/lazy cakes and the
combined source, integration-method and sparse-layout project round trip.

Primary integration checks: 147 Rust tests passed (one optional performance
benchmark ignored), Clippy with warnings denied and rustfmt passed, 79 frontend
unit/architecture tests and the production build passed. HDF5 source selection,
image-change/reset, projects/configurations/combination and the main native
workflow passed in headless Chromium and WebKit. Logs are in
`artifacts/hdf5-primary-integration/`; no visible test windows were opened.

# Native projects and configurations

The default Rust processor now opens and saves current format-2 `.dio` projects
through the existing React/Tauri Open project and Save project actions. A
configuration toolbar supplies Select, Add, Duplicate, Rename and Remove in
Calibration, Mask, Integration and Map. Python is now an explicit comparison
backend. These controls are exposed when the backend advertises native
configuration support; this change does not add configuration commands to Python.

## Ownership and workflow

Each configuration owns its image, calibration and picks, user/plugin masks,
processing and integration settings, backgrounds/flat response, curves, Batch
and Map. Switching retains its in-memory calibration/integration and mask
Undo/Redo histories. Add follows Qt's core behavior: it starts with the current
processed image and calibration and fresh processing settings. Duplicate copies
the complete configuration. Phases and overlays remain shared across the project.
A configuration's ordinary Undo cannot revert shared edits made elsewhere.
Shared phase/overlay edits invalidate older shared-edit history in inactive
configurations; undo those edits from the configuration where they were made.
Histories are session state and are not serialized into `.dio`.

Runtime configuration identities reset plot/draft contexts and stop stale live
Map work even if a new project reuses the same configuration index. Incoming-file
processing and automatic saving are disabled on project load, matching the
existing desktop behavior. Source files and authored material records are not
changed by opening, switching or saving projects.

## File compatibility

The reader/writer uses the existing format-2 JSON `/state`, `/payloads`, `/cache`
and per-configuration Map groups. Native output is read by the current Python
project reader, and current Python output is read and resaved by Rust. Unknown
JSON fields, root attributes, and unrelated HDF5 objects are retained in an owned
archive; configuration groups are reindexed with their preserved contents when
configurations are duplicated or removed. Known scientific state is rewritten
from the current session.

Ordinary format-2 saves rebuild a compact HDF5 file rather than accumulating
free blocks from older saves. Unreferenced f64 hash entries in the owned cache
and payload pools are removed. Reachability includes unknown JSON fields,
string metadata and symbolic links; metadata whose references cannot be safely
classified conservatively retains the pools. Unknown objects, attributes and
hard-link aliases are preserved. Original cached float64 bits, including
nonfinite values and signed zero, are retained.

Archives containing HDF5 object/region references, hard links to the root,
user blocks or external/virtual dataset storage use a conservative byte-copy
compatibility path. It retains object addresses and replaced reference targets,
rather than attempting a general HDF5 reference rewrite. These opaque archives
are not compacted; a duplicated configuration cannot be published from such an
archive because copying it could change extension reference addresses. The
native session and preceding output remain intact on that explicit error.
Both compact and compatibility saves reject a result above the same 16 GiB
physical-file bound used by the reader, before atomic publication.

Cached detector images, image backgrounds and flat responses are owned by the
project and load without their original source files. Raw caches preserve the
bottom-up scientific convention, including nonfinite detector values. Scientific
arrays remain f64; f32 display rasters are separate. Subsequent source navigation
or reintegration still needs the original files and dataset selection. Original
source dtype is not recorded by the existing cache format; restored raw caches
are represented as f64 without claiming their original storage type.

Optional native metadata adds labels, custom calibrant text and workflow/fit
state per configuration, reader options, inactive correction drafts, and complete
per-configuration Batch/Map normalization state. The existing selected-config
`react_desktop`, `react_desktop_batch` and `react_map_normalization` documents are
also emitted for the Python desktop. Batch stores its selected row, background
matrix, original normalization arrays, complete source frame counts and position
maps, including frame range/stride selections.

Older Qt/Python writers can discard native extensions when saving again. Base
scientific project data remains interoperable within the supported boundary;
labels and inactive-configuration Batch/workflow extensions are not guaranteed to
survive a save through those writers. This is not universal lossless roundtrip
qualification for every historical `.dio` file.

## Failure behavior and current limits

Opening builds candidate configurations before replacing the live session.
Saving writes, flushes and syncs a temporary sibling before atomic publication.
Failures and cancellation retain both the preceding session and an existing
save target. The archive keeps both an open OS file descriptor and a read-only
HDF5 handle, so temporary-path cleanup cannot prevent a later Save As.
Loads use an immutable copy and reject a source project changed
during restoration. Cancellation is checked between copy chunks and restore/save
stages; an individual HDF5/library call is not interrupted internally.

The current reader accepts format 2. Legacy formats 0/1 and future versions fail
explicitly, as do active unsupported plugins and science outside the native
adapter's supported boundary, including unsupported thermal-pressure settings.
Named/nonuniform/oriented/spline detectors are now supported within the
[detector ledger](NATIVE_DETECTOR_PARITY.md), including its legacy transformed-project limits. Image rotations/flips and geometric
masks are now implemented in [the next stage](NATIVE_GEOMETRY_MASK_PARITY.md).
Disabled unknown plugin state is retained. Legacy files need a compatible original reader and
explicit data export; resaving in the current Python reader is not a legacy
conversion path. Remaining geometry/masking/package work is listed in
[the backend migration document](backend/README.md).

Bounds are 64 configurations, 16 GiB input files, 64 million samples per science
array, 256 million aggregate materialized project samples, one million series
frames and four million Map cells. Aggregate arrays are checked before loading
and before publishing a save. These are memory bounds, not performance promises.

## Reproduce the checks

From the repository root, using the test-only Python reference environment:

```sh
cargo fmt --manifest-path desktop/backend/Cargo.toml --check
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --all-targets --all-features -- -D warnings
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --all-targets --no-default-features -- -D warnings
cargo test --locked --manifest-path desktop/backend/Cargo.toml --no-default-features
cargo test --locked --manifest-path desktop/backend/Cargo.toml --all-features
cargo build --locked --manifest-path desktop/backend/Cargo.toml --all-features
.venv/bin/python desktop/scripts/generate_native_project_schema.py
.venv/bin/python desktop/scripts/native_project_parity.py
.venv/bin/python desktop/scripts/native_series_parity.py
cd desktop
npm test
npm run build
npm run test:native-project
npm run test:native-project-transport
```

Rebuild the all-feature processor after no-feature tests: integration tests can
replace the debug executable with the feature variant under test. Python is
used only as an independent test reference; native test children run with Python
and PATH unavailable.

Project checks cover two configurations with separate integration settings,
shared overlays/phases, image masks/backgrounds/flat fields, two maps, reversible
normalization, selected Batch rows and source stride metadata. They compare both
reader directions, project-owned offline caches, authored materials/reflections,
custom calibrants/picks, preserved unknown objects, configuration removal, and
atomic rejection of corrupt or unsupported files. Rust tests also cover
nonfinite image caches and shared-background removal/history behavior.

The real stdio test observes progress and cancels in-flight save/load across 16
1024-square cached images; it compares the prior target bytes and complete
session state and rejects mutation of the original project during restoration.
Headless Chromium and WebKit exercise the actual add/duplicate/rename/select/
remove/save/open controls and render Integration and Map without command or
render errors. Receipts and screenshots are under ignored
`desktop/artifacts/native-project/`. Native dialogs, visible Tauri windows and
Windows/Linux execution are not requalified by these headless checks.

Checkpoint, 2026-11-07: native tests pass with and without Dioptrin (32/26),
strict Clippy passes in both feature modes, all 19 Tauri host and 60 JavaScript
tests pass, and the frontend production build passes. Project cross-reader,
transport cancellation and both browser workflows pass. The existing calibration,
masking, integration, processing, series, phase and I/O/history comparisons and
Chromium/WebKit workflows also pass after the shared-history and source-mapping
changes. This checkpoint does not qualify unsupported geometry or legacy files.

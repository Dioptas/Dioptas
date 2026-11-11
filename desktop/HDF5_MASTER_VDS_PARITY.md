# HDF5 master files and explicit source contracts

The HDF5 implementation lives in **dioptrin-io 0.3.0**, consumed through the
released `v0.3.0` tag at `dc6e30394e4374350020f8e1335f805f19e8364e`.
The [Rust source release](https://github.com/CPrescher/dioptrin-io/releases/tag/v0.3.0)
includes the source-contract APIs; Dioptas needs no private library branch or
local dependency override. Its source-contract resolver shares the typed
reader's actual dataset/convention selection and native link resolver. The
library also owns image-candidate enumeration and wrapped VDS/raw storage APIs.
Dioptas supplies user choices, session ownership, persistence and controls; it
contains no new HDF5 mapping engine, decoder or scientific fallback.

## Loading

Open image / Load image follows the exact external-link graph using native
FollowSnapshot. Ordinary relative Eiger masters open directly, concatenating
parts in the existing native order. Automatic and explicit dataset choices,
master aliases, independent frame/file navigation and detector-change decisions
retain their existing workflows. The explicit `follow_external_links:false`
command/project policy still rejects external links. The library's defaults
remain Reject; the desktop intentionally opts in for normal file loading.

The library derives VDS and external-raw contracts from actual declarations.
Relative names resolve against their physical owner; absolute names stay
absolute. Missing VDS/raw files open a compact **HDF5 source files** dialog with
original names, owners, exact expected paths and native file choosers. Choosing a
local copy binds that exact owner/name pair; it does not rename or edit a master.
Printf declarations ask for an explicit finite source-block count, bounded by
the native limit. Neither the library nor the UI scans neighboring filenames,
infers counts from availability or fills missing sources.

Unresolved sources remain selectable with **needs sources** and null count/shape
metadata. Their frame counts are unknown until admission. Generic loading tries
the first candidate in sorted alias order; an unavailable first source is not
replaced by another dataset. Recognized automatic selections remain independent
of an unrelated catalog failure, with the actual discovery error retained.

## Counts, ownership and failure behavior

The same wrapped native reader and binary buffer path own typed original
samples, orientation and geometry. Generic VDS/raw reading remains valid when a
source does not qualify for resident/combined loading. The existing narrow fast
paths retain their admission and source checks; no performance claim is added.

Pending source choices freeze the master and available companions. Cancel and
Escape publish nothing; changed metadata/files or invalid choices require a
fresh explicit open and preserve the preceding session. The native decoder
rejects cycles, overlaps, missing datasets, incompatible source shapes,
unallocated/truncated storage and layouts beyond its admitted boundary.

Each configuration retains source selection, explicit choices and acquisition
identities. Format-2 `.dio` caches remain project-owned and reopen offline.
Navigation/reconnection checks original file length, timestamps and object
identity, plus the live reader's native graph guards; changed companions are not
silently accepted as the old acquisition. Fresh Open image establishes a new
snapshot. These are metadata-based immutable snapshots, not a cryptographic
claim against adversarial timestamp-preserving edits.

Decoded private captures of compressed masters are transient transport data.
They are not persisted as acquisition files. The encoded master and external
companions define reconnect and Batch/Map identities, while the live wrapped
reader retains and validates its private capture. Development checkpoints use
that same owned-cache/source distinction.

Batch/Map retain reader options and source identities for each input file.
Selecting stored rows or reintegrating uses the series' source, even after the
current image switches datasets. Native processed-series metadata, `.dio`
projects and development checkpoints retain these contracts. Older series
without this optional metadata retain their previous compatibility behavior.
An append cannot replace the contract for a file already in that series.
Aggregate source metadata is bounded at 16 MiB, consistent with the existing
processed-series read bound.

## Qualification (November 11, 2026)

Generated fixtures are explicitly separate from acquired data:

- Rust-created relative external Eiger masters with two companions, a soft alias,
  automatic/explicit switches, exact U16 values and all frame positions.
- Finite and nested VDS, a nonuniform original-word ramp and original row order;
  missing absolute companions with explicit choices and a mixed-source catalog.
- Split raw windows crossing a U16 word boundary, with prefixes/trailers excluded.
- Overlaps, cycles, invalid windows, changed masters/companions, native
  cancellation and complete state rollback; independent configurations,
  project-owned offline caches, exact reconnect and development checkpoints.
- Batch/Map integration, selection after source changes, stored-pattern ratios
  calculated independently from fixture scale factors, project persistence and
  reintegration. Compressed-master reopen and Batch tests check transport ownership.

`cargo test --locked --manifest-path backend/Cargo.toml --test hdf5_master_vds
--test hdf5_sources` runs those desktop regressions. The library's six focused
contract tests additionally compare original finite/nested/printf words against
independent existing CC0 manifests, test stream origins/wrong-input contracts and
exercise separate raw bindings. Its full all-feature suite has 420 passing tests;
no-default-feature tests and strict Clippy also pass.

`npm run test:hdf5-master-vds` and `npm run test:hdf5-sources` use the real Rust
stdio processor in headless Chromium/WebKit. The new workflow checks standard
loading and both source selectors, companion chooser/cancel/Escape behavior,
frame navigation, project reopen, nested/raw inputs, explicit printf counts,
retained detector-size prompts and compact layouts at both text sizes. No
visible windows or real mouse/focus operations are used. Receipts/screenshots
are under ignored `artifacts/hdf5-master-vds/` and `artifacts/hdf5-sources/`.

The acquired `/Users/clemens/Programming/Dioptrin/test_data/eiger_0000.h5` has
625 frames at 3262 × 3108 in U32. The new standard path's original stored words
at frames 1, 313 and 625 match independent h5py/HDF5-plugin SHA-256 signatures.
`hdf5_counts_probe` and `scripts/hdf5_master_acquired_reference.py` reproduce
that explicit oracle; the receipt is `artifacts/hdf5-master-vds/acquired-eiger.json`.
The acquired Lambda inputs referenced by the pinned library's older ledger were
unavailable at their recorded local paths, so that older decoder proof is not
claimed as a new desktop acquired-master test.

## Limits

Support follows the native typed reader's qualified finite/nested/irregular,
frame-axis unlimited and explicitly bounded printf contracts. The UI uses only
defined original VDS fill for genuinely unmapped regions. Missing concrete
samples never become fill. Native unsupported cross-axis unlimited/point layouts,
VDS leaves with raw-external storage, unsupported types/filters and source limits
remain explicit errors. Identical stored filenames requiring different requested
paths in different physical owners exceed the native global filename contract
and fail explicitly. External-link filenames retain their exact metadata
semantics; this change does not add an external-link relocation editor.
There is no live/SWMR refresh, Python fallback, second scientific session or
universal beamline-support claim.

Desktop verification also passed the production build, 117 frontend tests, a
265-test full native checkpoint (two existing opt-in checks ignored), the final
16 focused HDF5 tests and 33 Tauri host tests. Strict backend Clippy reports the
pre-existing `items_after_test_module` lint in `phases.rs`; with that single
baseline lint excluded, all targets pass with warnings denied. The library's
strict all-target/all-feature Clippy passes without exclusions.

## Primary integration

Desktop commit `793fcdca` was fast-forwarded into `codex/rust-desktop` with all
18 pre-existing modified/untracked files preserved byte for byte. The primary
build and all 117 frontend tests pass. Its full native suite passes 269 tests
(two existing opt-in checks ignored), including the concurrent local Phase work.
The new HDF5 workflow passes in headless Chromium and WebKit against the primary
processor. The older source-layout fixture now targets Image controls explicitly
when both Image and Pattern controls exist in the current workspace. Its
alignment checks use the actual Image container width, including the existing
≤540 px compact toolbar rule in a multi-column task panel.
Evidence is under `artifacts/hdf5-primary-integration/`; unrelated local changes
and user previews/processes were retained.


## Versioned library release

The source-contract code was incorporated into dioptrin-io 0.3.0 on its default
branch and published as the immutable `v0.3.0` Git/source release. The desktop
manifest now selects that tag and its lockfile resolves the release commit.
The numerical Dioptrin engine stays on its existing 0.12.0 revision.

Release qualification passes the five-platform Rust/inventory/consumer matrix,
including Windows x64/ARM64 SIMD benchmarks, plus the six Python compatibility
jobs. The Python distribution remains independently versioned at 0.2.0. The
Windows-specific source-path assertion was corrected for native path semantics;
production reader code is identical to the initially qualified implementation.

# Validated Opus review fixes

This stage addresses the validated findings from the independent review of
`bd3a8359`. Scientific processing stays in Rust/Dioptrin over Tauri-owned stdio.
The existing interface, numeric conventions, image ownership and Integration-only
acquisition policy are retained.

| Finding | Implemented change | Regression evidence |
| --- | --- | --- |
| F1: project growth | Ordinary format-2 projects reuse configuration objects, remove unreachable owned cache/payload arrays, and compact into a fresh HDF5 file before atomic publication. | Repeated unchanged reopen/save, nine image/mask replacements, extension references, root attributes, aliases, and exact nonfinite/negative-zero cache bits. |
| F2: output permissions | One private staging/publication module honors kernel umask for new files and preserves existing target mode. | Subprocess umask 022/077, existing 0664 targets, private staging, aborted output and cancellation at publication. |
| F3: output failure recovery | Acquisition classifies autosave failure separately and retries the unchanged source after output repair. Successfully generated outputs remain excluded even after a later format fails. | Actual blocked-output repair, multiple pending images, partial multi-format writes, exact integrated output. |
| F4: own-output ingestion | Generated outputs are excluded by file identity, with immediate inode replacement detection, bounded rotating checks for in-place changes, and a final overwrite guard. Legitimate detector `.dat` inputs remain admissible. | Real `.dat` export, valid detector `.dat`, replacement preserving mtime, and source protection through directory aliases. |
| F5: delayed HDF5 companions | Declared missing or incomplete HDF5 dependencies enter a change-triggered retry queue; background polling emits no source modal. Companion arrival can recover an unchanged master, while permanent inputs fail quietly. | Raw external storage and Eiger links outside the watched directory; unchanged master bytes/mtime; later ready sources are not starved. |
| F6: acquisition scaling | Polling enumerates once, avoids stamp reads for unchanged known inputs, and drains an ordered bounded prefix. | Zero explicit stamp reads for 100 known files; ordered 12-source backlog; eight-attempt bound; complete exports and combined-product cancellation/resume. |
| F7: repeated metadata | Each client optionally advertises content tokens for Batch/Map metadata. Unchanged products reuse pinned metadata and raster owners; legacy clients still receive full results. | Real stdio/TypeScript roundtrip, independent clients, changed/null products, concurrent replacement, cache eviction/budgets, mixed arrays, and Tauri host roundtrip. |
| F8: inherited output pipes | Launcher exit and output-stream lifetime are separate. One bounded drain service preserves descendant writes; per-run state isolates deletion/rerun. UI polling continues for pending output. | Late descendant output after launcher completion, deletion/reuse isolation, admission release, and real Chromium/WebKit controller polling. |
| F9: archive pathname loss | Open projects retain both their read-only HDF5 handle and OS file descriptor; saves copy from the retained descriptor. | Save As after unlinking the snapshot and removing the original source. |
| F10: checkpoint copies | Watcher collections, Series source paths/counts/reader contracts and Map slots share storage; mutation uses explicit copy-on-write. Existing shared scientific arrays remain shared. | Actual checkpoint pointer sharing, isolated mutation, restore identity, append and processed-HDF5 roundtrip. |
| F11: launcher reaping | Documentation launchers transfer their Child to an asynchronous waiter. | Owned fake child is reaped with its exit status; no browser is opened by the regression. |

## Persistence compatibility

Ordinary projects compact and prune native pools. Unknown JSON/string references,
HDF5 attributes and aliases are preserved. Archives containing opaque object or
region references, root cycles, user blocks, external storage or virtual datasets
use a conservative byte-preserving path; that path can still grow. Its final
16 GiB bound is checked before publication, and unsafe configuration duplication
is rejected atomically. These limits preserve extension addresses and external
data. See [project compatibility](NATIVE_PROJECT_PARITY.md) for the exact boundary.

## Acquisition and cancellation

The frontend retains its existing one-second Integration-only timer. One poll
attempts at most eight images or 50 ms of work, checking that budget between
frames; a decoder or numerical library call remains cooperative. Each frame's
ordinary and combined products finish before its transaction commits. A later
cancellation preserves completed frames/exports and requeues the current frame.
Unchanged permanently unreadable inputs wait for a source change. Declared HDF5
companions are watched by file identity, including missing-to-present and partial
storage changes. Generated-output identity probes are capped at 32 per scan;
in-place replacement is detected within a complete rotation, while a final
identity check protects every automatic overwrite.

## Metadata and resource ownership

`cachedProducts` is optional transport metadata, outside scientific payloads.
The complete product JSON determines each token. Per-request pins retain the
advertised product/raster identities through concurrent replies. Cache accounting
includes retained binary packet owners; oversized products keep full transfer.
Warm references reuse their stored accounting without traversing the product.
Native snapshot construction/content hashing still visits metadata. See
[the command contract](COMMAND_CONTRACT.md).

Custom actions keep at most 64 admitted process/output lifetimes and 16 KiB of
captured text per run. Completed launchers release Run/Delete while inherited
output drains through EOF. Readiness-based draining preserves bounded fairness
without imposing a fixed byte-rate delay on chatty programs. Owned Unix
subprocesses mark non-stdio descriptors
close-on-exec, preserving configured stdio and Rust's exec-error channel. A
parent-only HDF5 gate covers fork through exec so inherited sec2 handles cannot
hold file locks after the parent closes them.

## Focused follow-up review

A second read-only Opus review of the fixes prompted additional acquisition
classification, bounded identity checks, extension-read compatibility and output
drain regressions. Traversal also now carries discovered HDF5 paths rather than
asking token-opened groups to search for their names. On the same local fixture
with 3,000 extension groups and 6,000 objects, save time changed from 77.662 s to
232.521 ms. This is a fixture measurement, not a general latency guarantee.
A suspected latest-format large-attribute failure was not reproduced; its
70 KiB attribute case is retained as a compatibility test.

## Verification

The native processor gate checks formatting, strict core-only lint and library checks,
all-target strict Clippy, all-feature tests and a normal processor build. Host checks prepare the real processor,
build the frontend and exercise Tauri's stdio ownership. The UI gate uses
headless Chromium/WebKit, including the new metadata and custom-action cases.
Independent Python references remain explicit test oracles, and the optimized
GLib regression plus live advisory/provenance checks remain enabled.

Run from the repository root:

```sh
node desktop/scripts/check_native_desktop.mjs --processor
node desktop/scripts/check_native_desktop.mjs --host
node desktop/scripts/check_native_desktop.mjs --ui
DIOPTAS_REFERENCE_PYTHON="$PWD/.venv/bin/python" node desktop/scripts/check_native_desktop.mjs --references
npm --prefix desktop run test:glib-backport
```

Detailed local receipts are retained under ignored `desktop/artifacts/opus-*`
paths. The implementation does not treat the original report's disproved
Dependabot/sys-lock claims or its overstated host-gate description as defects.

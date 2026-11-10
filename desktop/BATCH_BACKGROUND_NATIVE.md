# Native Batch backgrounds

Implemented and qualified in the Rust desktop on November 10, 2026. The runtime
uses the existing Tauri-owned stdio processor; Python/Qt are independent references.

Batch → Options contains Smooth width (in the recorded
fitting unit, initially the stored source unit), Iterations,
Polynomial order, Apply background settings and Extract background. Extraction
processes every stored row, including stored-only batches, and keeps the complete
previous background until all rows succeed. Progress and cancellation use the
existing worker control channel; cancellation checkpoints occur within the
Bruckner scan as well as between smoothing, fitting and frames. The detached
window routes mutations through the main window, including its Cancel control.

Original / Subtract bg are available beneath the overview and in Options, in
both docked and detached views. The manual Cut range button and duplicate Batch
range editors have been removed. Automatic pattern background updates retain
the pattern's fitted range and show only the covered bins. Separate full-axis
Batch extraction keeps its original behavior. Previously saved range/cut state
and the native compatibility commands remain readable and reversible.
Setting changes for separate extraction retain the current background and mark
it stale until extraction is explicitly repeated.

The Qt reference is `BatchController.extract_background`, `subtract_background`,
`plot_batch` and `_get_x_range`, `BatchModel.extract_background`, and xypattern
1.2.4 `SmoothBrucknerBackground` / Cython `smooth_bruckner`. Qt fits the full
stored axis; range cutting changes the overview only. The native implementation
ports the same padded, in-place Bruckner scan with cancellation checkpoints and
reuses the Integration Chebyshev fit (column-scaled SVD / NumPy rank tolerance).
Descending d axes retain their original scan order: reversing before smoothing
would change the result. The shared polynomial helper now permits either axis
direction without changing ascending-axis behavior.

Extraction uses the current un-subtracted intensity scale, including active
normalization, matching Qt. Its retained source-scale background supports later
normalization changes. Fitting the original raw scale and only then scaling the
fit is **not** an equivalent replacement for Qt's finite-precision smoother,
especially when the width truncates to a zero-point window. The native path
preserves that numerical behavior. Normalization and subtraction never feed
back into the retained original intensity matrix. Counting std and azimuthal
std scale only with normalization; the fitted background is treated as
deterministic and supplies no additional statistical error model.

New raw Batch integrations inherit the active Integration pattern background and
start in Background subtracted mode. This includes fitted automatic backgrounds,
loaded/captured backgrounds, their combination, and the fitted range. The native
pattern pipeline is reused on each stored row in the pattern's actual unit;
there is no resampling or reuse of the selected frame's fitted curve for other
frames. A restricted fit/overlay overlap cuts the overview to the covered source
bins; the retained background is zero outside that region without extrapolation.

Existing batches update automatically whenever the Integration pattern background
changes: enable/disable, width, iterations, polynomial order, fit range, loaded
background selection/removal, and changes to its scale, offset or data. Undo/Redo
of those edits updates Batch in the same transaction. There is no Apply step.
Ordinary overlay name/color/visibility changes do not trigger a series refit.

The live pattern editor retains its debounced, serialized latest-settings queue:
one calculation runs while subsequent edits replace the pending request with the
newest settings. Controls stay editable. Quiet background work now exposes
progress and cancellation in the shared footer and detached Batch window. A
cancellation or failed row rolls back both pattern settings and Batch products.
Consecutive quiet jobs capture the current progress generation on every poll so
a completed request cannot suppress progress for its successor.

Opening a processed file or project and switching configurations retain their
saved display choices. Only a new background edit updates the active Batch. The
manual Batch extraction/display controls remain available as an explicit
alternative; the next pattern-background edit restores the automatic result.

Applying a background never changes the original/normalized stored intensity
matrix or counting std. Selecting a row still restores that un-subtracted profile
before Integration applies its own settings, so the linked pattern never
subtracts twice. Background actions do not reload detector frames or alter Map
data. Map imports retain the un-subtracted matrix and discard Batch display state.
Stored-only rows now have a real "Stored pattern" label, enabling their pattern
background controls without inventing an external source filename.

Native `.dio` projects and the existing processed HDF5 format retain full-axis,
un-subtracted data, background, original normalization arrays and background
parameters/range/display flags. Qt can read the ordinary data/background datasets
and ignores the optional native metadata. A synthetic empty source path in an
HDF5 file is not shown as a real raw file. Project configurations own independent
background states. This work adds no export format or export option.

Intentional support differences and bounds:

- The Qt controller's range-to-bin calculation assumes a uniform angular axis.
  Native cutting selects source sample centers and therefore works on nonuniform
  or descending d axes without dropping/reordering the retained matrix.
- Widths must be 1e-6–1e7 source units, iterations 1–99999, polynomial order
  1–1000. Smoothing padding is bounded at two million points, the existing
  polynomial matrix at 16 million entries, and the SVD work estimate
  `samples × (order + 1)²` at 200 million. Invalid/nonfinite inputs fail atomically.
- The polynomial SVD itself is not interruptible; its size/work bounds limit
  that stage. Smoothing can be interrupted inside a row.
- A legacy HDF5 background without parameter metadata remains usable but its
  original fit parameters cannot be recovered.

Verification:

- `cargo test --locked --manifest-path desktop/backend/Cargo.toml --all-features`:
  four background numerical/model tests and four native command/ownership tests
  alongside the existing native suite. Independent Qt reference matrices cover
  2θ, Q, descending nonuniform d, orders 8/12/50, normalization before extraction,
  repeated extraction/toggles, exact source/std restoration, full/range views,
  stored-only selection, stale settings, invalid/cancelled operations, Map
  isolation, independent configurations and HDF5/`.dio` save/reopen.
- Numerical comparison uses every f64 background sample, with tolerance
  `2e-9 × max(1, |reference|)`. Normalized intensity references are compared too.
  The independent generator is `scripts/generate_batch_background_reference.py`;
  it requires the checkout's CPython 3.13 reference environment. Its small input
  HDF5 files and JSON outputs are frozen in `backend/tests/fixtures/`.
- `node --test desktop/scripts/batch_background_transport.test.mjs`: actual
  Python-free Rust stdio progress and mid-row cancellation, complete rollback of
  settings, selection and products, and no stale progress after completion.
- `node desktop/scripts/batch_background_smoke.mjs`: headless Chromium/WebKit,
  normal/large text at 1000 × 700, options scrolling, automatic pattern range handling, normalization,
  original/subtracted toggles, footer cancellation, detached mutation routing and dock restoration,
  invalid drafts and stale settings. Screenshots and receipts are written under
  ignored `desktop/artifacts/batch-background/`. No visible windows are opened.
- Frontend build, JavaScript unit/architecture checks and native Clippy are part
  of the focused validation. The headless/transport scripts are registered in the
  existing native CI gate and need no Python runtime.

The already-integrated waterfall feature was reconciled at its existing series
boundary: visible rectangle columns translate back to full source-bin indices,
subtracted intensities match the overview, counting std stays aligned, and a
background/cut change invalidates pending rectangles. A native interoperability
test covers these cases alongside the waterfall feature's original tests. No
new waterfall, 3D, or export workflow was added by the background implementation.

Combined qualification after reconciliation with the existing waterfall, 3D and
export commits: **169 native tests passed, one opt-in benchmark ignored; 85
JavaScript tests passed**. Frontend build and Clippy with warnings denied passed.
Background, waterfall, 3D and export headless checks passed in Chromium and WebKit;
background stdio and footer cancellation passed. The broader native Integration
browser regression also passed. These are headless/native-processor checks, not
OS-window or release-packaging qualification.

Pattern inheritance regression checks cover real raw integrations and stored-only
2θ/Q/d series, normalization, source and fitting units that differ, range cutting,
loaded backgrounds plus automatic fitting, repeated application, exact source/std
restoration and project reopen. Every corrected Batch sample is compared with
its corresponding native pattern-view sample. The headless test operates the
actual Integration checkbox and automatic update in both browsers;
stdio cancellation interrupts both manual and inherited fits inside a row.

Pattern-inheritance qualification: 185 native tests passed (2 opt-in benchmarks ignored), 95 JavaScript tests passed, and build/Clippy passed. Chromium/WebKit background and native-workflow checks and stdio cancellation passed.

Automatic-update regressions additionally cover parameter and ROI edits without
an Apply command, loaded-background transforms, Undo/Redo, project restoration,
source/Map isolation, an invalid later frame with whole-command rollback, rapid
coalesced edits, detached metadata/matrix refresh and quiet-job footer cancellation.

Live-update qualification: 188 native tests passed (2 opt-in benchmarks ignored), 95 JavaScript tests passed, and frontend build/Clippy passed. Chromium/WebKit passed automatic edits, coalescing, detached updates, quiet-job cancellation, and the broader native/Integration browser checks.


Performance optimization (November 10, 2026):

The shared-axis Chebyshev matrix and column-scaled SVD are now prepared once per
operation, rather than once per pattern. Each row still receives its own
Bruckner smoothing and least-squares solve. A private Rayon pool uses up to three
workers for independent rows in both automatic updates and separate extraction.
The actual pattern pipeline prepares the first row, including ROI and loaded
background overlap, then shares its immutable fit plan with worker-local pattern
state. The smoothing scan and floating-point operation order inside every row
are unchanged. Workers write disjoint scratch rows; only a complete successful
matrix replaces the retained background. Failed rows stop peers at row boundaries;
cancellation is also checked within smoothing. Progress counts completed rows
under a lock and publishes at most about every 40 ms, plus completion.

On the active 625 × 1000 stored batch, width 0.1, 150 iterations, order 50 and
872 covered bins, three complete Rust stdio updates measured:

| Implementation | Median time | Speedup from original |
| --- | ---: | ---: |
| Original per-row decomposition | 2414 ms | 1× |
| Shared decomposition, serial rows | 441 ms | 5.5× |
| Shared decomposition, three workers | 176 ms | 13.7× |

These are local development-preview measurements including fitting, Batch
products and the native reply, excluding React rendering. They establish this
workload's improvement, not a universal speedup. Every retained f64 background
sample (625,000), original intensity sample and radial-axis sample was compared
bit for bit with the pre-change executable; all matched. Saved numeric metadata
matched too. The aggregate receipt is
`artifacts/batch-background-performance/summary.json`; private scientific matrices
and source paths are not committed. Reproduce with
`scripts/batch_background_benchmark.mjs input.h5 parameters.json receipt.json result.h5`,
using `DIOPTAS_NATIVE_PROCESSOR` to select a baseline executable.

Qualification: 188 existing native tests passed (two opt-in benchmarks ignored),
plus a new bitwise serial/parallel comparison with 37 unevenly partitioned rows.
The independent Qt fixtures continue to cover descending d, normalization and
order 50. JavaScript's 95 tests, frontend build, Clippy with warnings denied,
Chromium/WebKit background controls and native stdio cancellation passed.

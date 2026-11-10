# Native Batch backgrounds

Implemented and qualified in the Rust desktop on November 10, 2026. The runtime
uses the existing Tauri-owned stdio processor; Python/Qt are independent references.

Batch → Options contains Smooth width (in the stored source unit), Iterations,
Polynomial order, Apply background settings and Extract background. Extraction
processes every stored row, including stored-only batches, and keeps the complete
previous background until all rows succeed. Progress and cancellation use the
existing worker control channel; cancellation checkpoints occur within the
Bruckner scan as well as between smoothing, fitting and frames. The detached
window routes mutations through the main window, including its Cancel control.

Original / Subtract bg and Cut range are available beneath the overview and in
Options, in both docked and detached views. Setting changes retain the current
background and mark it stale until extraction is explicitly repeated. A range
can be set or cleared independently of extraction. It uses inclusive stored
sample centers, preserves acquisition/column order and converts labels with the
recorded wavelength; Q ↔ d also works without a wavelength. It never infers an
angular wavelength for stored-only data.

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

As in Qt, Batch overview subtraction/cutting and the linked Integration pattern
are independent. Selecting a row restores its original (or normalized) stored
profile and counting std, while Integration keeps its own pattern background
settings. Background actions do not reload detector frames, change selection,
alter Map data, or apply another subtraction to the linked pattern. Map imports
retain the un-subtracted matrix and explicitly discard Batch display state.

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
  normal/large text at 1000 × 700, options scrolling, range cutting, normalization,
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

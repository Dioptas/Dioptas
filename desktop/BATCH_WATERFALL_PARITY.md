# Native Batch rectangle to waterfall overlays

Batch → 2D → **Waterfall** arms primary-button rectangle selection in both the
dock and detached window. Drag across radial bins and frame rows to replace the
shared Integration overlays. Integration opens its existing Overlay controls;
Spacing/Waterfall, scale, offset, color, visibility, ordering, background use,
and removal retain their existing owner. Changing the existing Batch **Step**
regenerates the selected rectangle. Turning the tool off or pressing Escape
cancels selection and retains completed overlays. Pointer cancellation never
creates curves. Secondary gestures, wheel, F fit and ordinary zoom outside the
tool keep the shared navigation implementation.

## Qt reference and intentional differences

The reference is `BatchController.waterfall_mode`, `process_waterfall`,
`plot_waterfall`, `process_step`, and `BatchWidget`'s 2D control group. Qt's
rectangle corners are truncated toward zero, sorted, clipped to the available
matrix and sliced with **exclusive upper endpoints**. Row selection is
`range(first, stop, Step)`; it starts at the selected first row, not an acquisition
multiple of Step. Selected columns remain in their original bin order. The
native overview projects directly into stored bin/row space, so a zoomed or
panned selection already includes its frame/radial offsets. No interpolation,
rebinning, integration or display-level transformation occurs.

The desktop uses a primary drag in place of Qt's two clicks. Its standard
four-pixel drag threshold avoids accidental actions. Empty slices reject
atomically and retain prior overlays. At most 1000 curves may be created,
matching the existing native project overlay limit; the error asks for a larger
Step or smaller rectangle. Each completed selection **replaces** the overlay
list like Qt, rather than accumulating duplicates. Unique overlay IDs are never
reused. Offsets use the existing Qt-compatible negative separation order.

## Scientific and persistence ownership

`backend/src/batch_waterfall.rs` slices the owned f64 Series data, counting std
and azimuthal std. Source axes are retained canonically; only overlay display
coordinates are converted to the current pattern unit, using each series'
recorded wavelength. This also handles nonuniform, descending d axes and
wavelength-free Q↔d conversion. Missing angular conversion information fails
atomically. √/log, histogram limits and palette remain display-only. Stored-only
series need no detector, raw file, calibration or reintegration.

Each overlay retains the scientific-series fingerprint, absolute row, exact
half-open source-bin interval, full file path, zero-based source frame, source
unit/wavelength and normalization flag. Human-readable names match Qt's
`basename, source-frame` convention, including duplicate basenames; identity
uses the full path and unique overlay ID. Selections carry a fingerprint of the
f64 samples/diagnostics, axis and entry map, so stale actions cannot select a
replacement acquisition merely because its f32 raster has identical bytes.

Normalization and restoration belong to Series. Generation never changes those
arrays or the stored frame selection, detector image, current pattern settings
or main-pattern background fit settings. It copies the current normalized
samples exactly and retains diagnostic scaling. Replacing the overlays detaches
any old overlay-as-background reference because that overlay no longer exists.
No Batch background fitting is implemented by this feature.

The shared overlay owner, native project arrays and existing history provide
save/reopen, configuration sharing, Undo/Redo and worker handoff. Project rows
save ordinary x/y arrays in the active unit for Qt readers, plus optional native
source-axis/provenance/std fields that preserve exact canonical samples in the
native reader. Old ordinary overlay rows remain readable. Source files are not
needed to reopen the generated curves. Rectangle-tool state is temporary; the
resulting overlays and their editing/separation state persist normally.

## Evidence

- `cargo test --locked --manifest-path desktop/backend/Cargo.toml --all-features`
  passed, including `tests/batch_waterfall.rs`: exact selected rows/bins across
  every 2theta/Q/d source/target pair, independent coordinate formulas, reversed
  endpoints, descending axes, clipping, stride, normalization/std propagation,
  repeated replacement, same-basename provenance, stale/invalid/cancel rollback,
  shared overlay Undo/Redo, edits and offline project round trips.
- `cargo clippy --locked --all-features --all-targets -- -D warnings` passed.
- `npm run build`, `npm test` (79 tests), `npm run test:ui-components` and
  `npm run test:functional-coverage` passed.
- `npm run test:batch-waterfall` passed in headless Chromium and WebKit against
  the real Rust stdio worker: reverse/repeated drags, Step regeneration, Escape
  and pointer cancellation, normal zoom/pan/wheel/F, detached command routing,
  overlay panel reveal and redocking. Screenshots are saved under ignored
  `desktop/artifacts/batch-waterfall/`.
- `node desktop/scripts/batch_navigation_smoke.mjs` passed in both engines,
  retaining frame selection and snapshot ownership behavior.

Only the legacy `test_create_waterfall` functional-coverage entry changes here.
Batch background fitting, 3D and bulk export remain separate feature owners.

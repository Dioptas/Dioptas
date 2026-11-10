# Native Batch export qualification — November 10, 2026

Batch **Save** offers processed HDF5/NXS, single-file CSV, per-frame XY/CHI/DAT/FXYE,
and PNG of the active Batch plot. Format selection uses shared UI controls;
the main Tauri host owns the native save dialog, including requests from the
separate Batch window. Explicit paths continue to bypass the chooser. The
existing HDF5/NXS and CSV writers and their normalization/background metadata
are retained.

## Numerical ownership and Qt behavior

`backend/src/batch_export.rs` reads the owned `Series` f64 arrays. It does not
select frames, load raw images, recalculate the current pattern, change
normalization or consult f32 display pixels. Stored-only batches work without
raw files or live calibration. All stored integrated rows and radial bins are
exported in their existing order; integration Start/Stop/Step has already been
applied. Selection, overview zoom and a background display cut do not reduce
numerical output. Names follow `BatchController.save_data`: `name_000.xy`,
`name_001.xy`, etc., with a minimum of three digits and zero-based stored-row
numbers, independent of source file/frame numbers.

XY, CHI and DAT contain radial coordinate/intensity pairs. The active Batch
unit is used, including the linked pattern unit while docked. Axis conversion
uses the recorded series wavelength; Q↔d requires none. Missing angular
conversion information is an error before publication. CHI retains its four-line
header. Data rows use 17-place exponential output to preserve f64 values.
Comment metadata records source path/frame, row, stored/requested/output units,
wavelength availability, calibration/mask, normalization interval/reference and
whether errors, azimuthal std and a background are available.

FXYE uses stored propagated **counting std**, never azimuthal std or
`sqrt(abs(intensity))`. Missing/nonfinite counting errors reject the export
without completing any output. This is an intentional difference from Qt's
legacy no-errors FXYE fallback. Q is written in Å⁻¹ (`CONQ`); 2θ uses centidegrees
(`CONS`). For a d display, native Batch converts to 2θ using the recorded
wavelength and records the requested/output units. It rejects this conversion
without that wavelength. This intentionally avoids Qt's legacy d/CONS output,
which labels scaled d coordinates as angles. The Save dialog explains the rule.

When azimuthal std exists, each frame also gets `name_000_spottiness.csv` with
radial coordinate, original integrated mean, population std and relative spread.
The cutoff is Qt's `1e-12 * max(1, max(abs(finite mean)))` per frame; nonpositive,
tiny or nonfinite ratios are NaN. Background subtraction does not alter these
observables. No sidecars or statistics are fabricated when spread is absent.

When a stored background matrix exists, matching `bkg_subtracted/name_000.xy`
files contain current intensities minus that frame's stored background. This
uses the native series background directly, including normalization, rather than
Qt's side effect of replacing/fitting the live pattern during export. Stored
counting errors are retained; fitted-background uncertainty is not estimated.
Export does not extract or fit backgrounds. The concurrent background feature
owns fitting, subtraction/cut display flags and its persistence extensions;
its current implementation retains `Series.data` and supplies normalized
`Series.background`, matching this boundary. HDF5 continues to call `Series.save`
so subsequent background persistence fields are preserved by their owner.

## Publication and images

Per-frame output is staged on the destination filesystem before any file is
published. Every final filename is checked, and publication uses hard links to
prevent clobbering, including concurrent collisions. An error or cancellation
rolls back files created by that attempt and removes a newly created empty
background folder. Cleanup failure explicitly lists remaining incomplete output.
Success returns the complete `savedPaths` list only after final cancellation
checking. A process crash can leave a subset of files but cannot report a
successful export; a later attempt refuses those names. Single-file exports
retain their existing atomic replacement convention.

PNG captures the active Batch canvas at its current device-pixel size, with
axes, ticks, radial units, selection/phase lines, zoom, palette, contrast and
linear/log/√ scale. It composites over the actual plot background and does not
include task controls or the histogram editor. Files, Options and collapsed
views cannot save a stale plot. Capture failures remain in the Save dialog.
The Rust worker validates/atomically writes the PNG. PNG is display data;
numerical export always uses f64 source arrays.

`src/batchCapture.ts` defines `BatchCapture = () => string | null` (base64 PNG
without a data URL prefix) and `BatchCaptureRef`. `BatchHeatmap` registers/clears
its capture with its lifetime. `BatchView` passes a separate compatible ref to
`BatchSurfaceView` and chooses the active 2D/3D capture for Save. It also accepts
an optional external `capture` ref. No extra dialog or scientific command is
needed for 3D images. The renderer and its camera controls remain owned by the
separate surface feature.

## Verification

- Seven focused Rust tests independently parse numerical rows and assert f64
  values, 2θ/Q/d conversion, valid FXYE coordinates/counting errors, Qt names,
  source frame order/range, background copies, normalization and HDF5/NXS
  readback, absent statistics, spottiness cutoff/NaNs and unchanged originals.
- Cancellation is injected at every staging/publication boundary, including
  after the last file; tests assert no completed output. Existing/concurrent
  collisions, nonfinite samples, unavailable angular conversion, missing errors
  and invalid/missing PNG captures cannot return successful saved-file lists.
- The reconciled processor suite passes 161 tests (one optional performance
  benchmark ignored), including the seven focused export tests; native Clippy
  passes for all targets with warnings denied.
- Tauri's 26 headless host tests pass, including native per-format filters,
  suggested extensions, explicit-path bypass and companion-window restrictions.
- Frontend production build and 85 JavaScript/architecture checks pass.
- `npm run test:batch-export` uses the real native processor and Chromium/WebKit
  headlessly. It exercises the detached-to-main save route, every format, source
  range, modal Escape/Cancel, chooser cancellation, failed existing-file export,
  unavailable image choices and unchanged scientific state. PNG decoding is
  compared pixel-for-pixel with the rendered canvas at 2× device scale using Q,
  √, zoom and Viridis; axes outside the image contain rendered text. Active 3D
  PNG bytes match the surface renderer exactly and differ from 2D. PNG and UI
  screenshots are visually inspected. Receipts/images: `artifacts/batch-export/`.

Native OS save panels themselves are covered through routing/unit checks here;
no visible/native test windows were opened. Windows/Linux filesystem and native
save-panel behavior are not newly qualified by this macOS/headless run.

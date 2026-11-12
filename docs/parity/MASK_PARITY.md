# Mask mode: Qt parity and verification

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `../architecture/REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](../architecture/REFERENCE_DATA.md) for retained fixtures and current checks.

Implemented on branch `codex/desktop-mask`, using the Qt sources in
`/Users/clemens/Programming/Dioptas` as read-only reference (2026-11-01):
`MaskWidget.py`, `MaskController.py`, `MaskModel.py`, `MaskPluginWidget.py`,
`MaskImgWidget` and the drawing items in `widgets/plot_widgets`.
The current Qt source and this checkpoint contain the same essential mask
operations, including radial range masking and the three built-in plugins.

| Qt workflow | Desktop implementation |
| --- | --- |
| Mask / unmask | Applies to point strokes, geometry, intensity thresholds and radial ranges |
| Circle | First click fixes the center; moving outward sets the radius, second click commits, matching Qt's `MyCircle` |
| Rectangle | Two clicks, either direction; row/column adaptation delegates to `MaskModel.mask_rect` |
| Point | Click to stamp; left-drag rectangle zoom; Shift-drag paints / erases continuous strokes, interpolated at source-pixel spacing; Ctrl-drag / right-drag pan; explicit diameter, Q/W adjustment |
| Polygon | Click vertices, double-click or Enter to finish; Escape cancels |
| Arc | Three points along the circle and a fourth point for width; the model's circumcenter, angular sampling and polygon rasterization |
| Above / below thresholds | Original image counts, strict comparisons via the mask model |
| Inside / outside radial range | Calibrated 2θ, q or d arrays, inclusive interval and optional open bounds; changing unit clears input bounds |
| Grow / shrink / invert / clear | Existing model operations, including their exact morphology behavior |
| Cosmic Removal | Same two LA Cosmic passes and parameters as `MaskModel.remove_cosmic`; cancellation between passes |
| Dynamic masking plugins | Runtime discovery, enable/disable, schema-based settings applied on Enter or blur, immediate checkbox/menu changes, Defaults with recomputation and imprint; built-in Threshold Mask, Cosmic Ray Mask and Spot Mask |
| File load / add / save | `.mask` (TIFF), NumPy, EDF and TIFF, shape and numeric validation, OR merging and native dialogs |
| Vertically flipped files | Explicit file-orientation checkbox, matching Qt's flipped NumPy/EDF choices; native chooser defaults to `mask.npy` when enabled |
| Use / transparency | Mask remains visible while editing; separate use switch controls processing, transparency changes the overlay only |
| Undo / redo | Existing application history, including edits, file loads, plugin settings/imprints and transforms; Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z and Ctrl+Y |

Clear, invert, grow and shrink operate on the user mask, as in Qt. Active
plugins remain separate until imprinted. Saving a mask writes the user mask;
imprint active plugins first to include them. Standard `.dio` persistence
retains user masks and plugin settings/enabled states. The optional external
plugin interface uses the existing plugin manager; no optional plugin or
Dioptrin engine is mandatory.

The point control consistently means diameter. Qt labels it as diameter but
passes its value as a radius; this interface intentionally resolves that
ambiguity. Circle selection follows Qt's integer center/radius conversion.
Edits and file loads enable Use mask, retaining the existing desktop preview
convention; switch it off to compare integration without the mask. Qt leaves
that switch unchanged while editing.

## Shared boundaries and integration notes

- `MaskView.tsx`, `MaskPanel.tsx`, `maskDomain.ts` and `mask.css` own the mode's
  layout, controls, preview construction and selection state.
- `RasterView` has opt-in props: `overlay` (source-pixel paths or ellipse),
  `onImageDoubleClick`, and `imagePadding` (Mask uses zero inset).
  Their defaults leave calibration/cake behavior
  unchanged. Shapes use the existing `onPick` hook. The renderer remains the
  only owner of coordinate mapping, orientation, zoom, pan, wheel capture,
  resizing and square-pixel display. No renderer or gesture code was copied.
- `ImageIntensity` supplies the Mask detector's own histogram, linear/log,
  levels, auto settings and colormap. Mask display choices are independent of
  calibration and cake choices. Mask-only undo retains image contrast and
  viewport, and does not dirty an unchanged calibration fit.
  While Mask mode is active, edits, mask files, plugins and undo/redo update
  the mask without integrating the image. Stale pattern/cake results are
  cleared and refreshed once when leaving Mask for any other mode, including
  Map and future modes; further mode switches reuse the refreshed results.
- `dioptas/desktop/mask.py` owns the command adapter. `session.py` only mixes it
  in, routes commands and exposes mask state. Existing brush/file operations
  moved out of shared session/calibration code. `mask_file` remains the native
  file command; `add` and `flipud` flags pass through the same Tauri chooser.
- `calibration.py` changes only mask alignment during image transforms and
  removal of the relocated file adapter. The mask transforms with source
  pixels, including reset and history restoration. A new mask is not created
  for each mode: calibration/refinement and integration read the configuration's
  existing mask. Single-thread scientific ownership and local stdio transport
  remain unchanged.
- Tauri smoke loads a separate mask interaction script after its existing
  real-image calibration test. No Vite port is used, and the primary preview
  on port 1420 is untouched.

## Validation

Real-model tests in `tests/test_mask_workflow.py` cover exact model geometry,
arc construction, threshold/radial arrays, grow/shrink/invert/clear, all four
file formats, flipped orientation, merges, rejected-file atomicity and redo,
project persistence, source pixels after transforms/reset, plugin
settings/imprint/history/persistence, LA Cosmic equivalence/cancellation and
mask effects on real pyFAI integration. `test_mask_bridge.py` additionally
checks progress/cancel bypass while the owning scientific worker is inside a
plugin computation and verifies rollback.

The final desktop, Qt MaskController/MaskModel and CalibrationController
suite passed **165 tests with five skips** (170 collected), including the
fit-diagnostic and threaded mask-cancellation regressions. Dioptrin was absent;
optional-engine tests skipped. The 20 mask-workflow tests and one owning-worker
cancellation test passed. The three Rust host/transport tests passed.

`npm run build`, existing `npm run smoke`, `node scripts/mask_smoke.mjs`,
`npm run tauri:smoke`, and `cargo test --manifest-path src-tauri/Cargo.toml`
exercise the real processing boundary. The mask browser script covers all five
selection tools, unmasking, preview cancellation, zoom/resize source pixels,
transformed images, file controls, plugin settings/imprint/undo, radial range,
independent image controls and compact/larger text layouts. The native smoke
covers mask selections, history, flipped NumPy file round trip and thresholds,
then returns to the preserved calibration validation. Native file chooser
routing/defaults also have Rust tests. Screenshots and JSON/log reports are in
ignored `artifacts/`.

## Remaining limitations

- Plugin algorithms have no internal cancellation callback. Progress/cancel
  requests remain responsive; cancellation discards the result when a plugin
  call returns. LA Cosmic cancellation is checked between its two passes.
- Plugin settings appear inline. Numeric/text edits apply on Enter or focus
  loss; checkboxes and menus apply immediately. Defaults resets and recomputes
  in one action. There is no separate Apply button. Qt uses a modal dialog
  with live recomputation and restoration on Cancel.
- Installed third-party plugins are discovered and schema-driven, but this
  validation uses the bundled plugins. Individual external plugins and
  cross-platform native file dialogs are not qualified by these checks.
- Mask mode has the detector image, as Qt's MaskWidget does. Integration and
  calibration validation retain their existing cake and pattern views.
  Mask display preferences reset when the mode is remounted; the scientific
  mask and plugin state persist in the configuration/project.
- This remains a source-checkout Tauri preview with local Python scientific
  processing. No portable Python bundle, Rust-only science or WASM execution
  is claimed.

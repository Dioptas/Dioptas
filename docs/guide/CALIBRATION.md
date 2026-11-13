# Calibration workflow

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

## Calibrate first

1. Open a calibrant image, or explore the raw CeO2 example.
2. In **Image**, check image orientation, detector and pixel sizes.
   Valid pixel-size edits apply when leaving the field or pressing Enter;
   there is no separate Apply button and the selected tab stays unchanged.
   Previous/next arrows sit beside **Open image**. Detector definitions and
   distortion files follow the transformation buttons, separated by a divider.
   **Load .poni** and **Enter manually** stay available as quiet footer actions;
   mask use, transparency and mask loading are directly below the detector
   tools. Processing uses the native Rust/Dioptrin backend.
3. The shared strip above the tabs shows **Ring**, **Auto advance** and **Pick peaks**.
   Previous/next buttons step through rings; the ring menu shows picked-point totals
   and supports number entry followed by Enter to jump to a ring. Clicking a
   peak-table row selects that group and updates the active ring. Auto advance
   increases the ring number after each selection. With Pick peaks enabled,
   stationary detector clicks pick peaks in any calibration tab; turn it off
   to navigate without adding peaks. **Peaks** holds automatic/single peak search,
   search size and the group table. Pick bright
   positions around the ring; use the group table to inspect or reassign picks.
4. Open **Fit**: distance, wavelength, PONI 1/2 and rotations 1/2/3
   each have a value and an independent fit checkbox. The defaults match Qt:
   geometry parameters free, wavelength fixed. The folder button beside the
   calibrant selector loads custom `.D` spacings. Wavelength/energy, starting
   distance, polarization and fit constraints live here, not on the Image step.
   Calibrate uses the current parameter values and fit checkboxes
   directly; there is no separate Apply step. The example supplies its own known
   fixture values. Select enough
   peaks for the free parameters and spread them across several rings.
5. In **Fit**, press the fixed **Calibrate** action at
   the bottom of the task panel. The **Refinement** controls below Parameters configure automatic
   ring searches using the selected Massif/Blob settings; its progress is shown and it can
   be cancelled. Numeric options apply on blur or Enter, without an Apply button.
   Disable it to fit only the manually selected points.
   **Calibrate** and **Refine** are available together on both
   Fit and Validate, with short explanatory tooltips. Calibrate starts a fresh
   geometry from the current peak selections, distance/wavelength start values
   and fixed parameters. Refine continues from the existing geometry and is
   enabled once a geometry has been fitted, loaded or entered manually.
6. Validate the ring overlays, cake, integrated pattern, and RMS residual.
   Linked click inspection is shared by Integration and Map. Change
   **Validation calibrant** to inspect a different reference without changing
   the geometry. Use the peak table to reassign groups, select/delete several
   groups, or undo/redo edits; refine again after editing selections.
7. Inspect or edit complete geometry through the visible **pyFAI / Fit2D** tabs,
   then save a `.poni` calibration with the general footer action, available on
   every tab. Geometry and fit drafts persist while switching tabs; apply
   geometry edits or refit changed selections before saving.
   Alternatively, use **Load .poni** or **Enter manually** from any tab, without
   picking peaks.
   The geometry in a saved `.poni` file describes the image as shown, after the
   rotate and flip buttons. The file records that view in a
   `# Dioptas image orientation: <view>` comment, next to `# Calibrant:`.
   pyFAI ignores both comments. Loading the file in Dioptas turns the open
   image to the recorded view; files without the comment keep the current view.
8. Switch to **Mask** for drawing, geometric selections, thresholds, automatic
   masks and mask files; see [Mask parity](../parity/MASK_PARITY.md). Switch to
   **Integration** for image/cake/pattern display, integration options, shared
   masks, backgrounds, corrections, overlays/phases and Qt-style pattern saving;
   see [Integration parity](../parity/INTEGRATION_PARITY.md). Calibration also offers mask load/use,
   image transformations, detector definitions, distortion splines, and custom
   calibrant `.D` files.

The image readout and peak-table positions count rows downward from the top.
The detector picture keeps its existing orientation. Scientific geometry and
stored control points retain the existing Dioptas bottom-left convention; the
UI converts row labels without flipping the data. See
[the calibration comparison](../parity/CALIBRATION_PARITY.md) for coverage and differences.

Display intensity limits, linear/logarithmic scaling, and color maps do not
change scientific arrays. Detector images, masks and cake arrays are transferred at their complete spatial
resolution (no display decimation). Zoom therefore resolves the original
detector pixels; calculations, brush edits and pixel readouts also use original
resolution. Display payloads use float32; scientific arrays retain their source
precision independently of the display buffers.

## Changing detector or image dimensions

Opening an image with different source dimensions first offers **Cancel** or
**Open and reset calibration**. Cancel preserves the current image, geometry,
mask, background, corrections and history. Accepting opens the new image without
calibration while retaining the current workspace and tab. It clears detector geometry,
pixel setup, distortion, picked peaks, masks (including enabled mask plugins),
image background/corrections and the previous integration/cake. Image orientation
returns to its original state. Load a matching `.poni` or check the detector/pixel
sizes and calibrate again. Wavelength/distance start values, integration
preferences, overlays and phases remain available; automatic saving and
Autoprocess turn off.

The small **Reset calibration** icon beside **Load .poni** offers the same reset
while retaining the current image. Use it when changing detectors even if the
new detector has the same dimensions. Ordinary same-size image loads preserve
the current calibration, mask and image processing. Rotation is accounted for
when comparing source dimensions.

Previous/next image and frame navigation use the same compatibility check.
Autoprocess stops with a message on a size change instead of silently applying
the old geometry. When a PONI declares detector dimensions, incompatible image
loads prompt even if no image was previously loaded; loading that PONI onto an
incompatible current image is refused. Legacy/custom PONIs without dimensions
cannot establish the expected image size, so their first image establishes it.
Equal dimensions alone cannot establish that a calibration belongs to a detector.

The native and headless image-change checks cover this workflow. Run
`node scripts/image_change_smoke.mjs` from the repository root for the real-model headless
workflow, or add `--webkit`. It checks confirmation, cancellation/Escape and
focus restoration, reset/reload, ordinary same-size switching and compact layout
at both text sizes. Evidence is written to `artifacts/image-change/`.

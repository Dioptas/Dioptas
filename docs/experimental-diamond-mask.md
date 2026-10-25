# Experimental diamond spot masking

These are experiments on the `codex/dynamic-spot-mask` investigation branch.
**They are not registered in Dioptas and cannot be selected in the GUI.**
The new compiled `DiamondROIDetector` meets the user's **less than 10 ms**
limit in the P1 benchmark below. Its preparation, supported input and remaining
scientific limitations are explicit; this is not a general performance guarantee.
The earlier NumPy/SciPy detector (2.94 s/frame) and sampled prototype (16.19 ms
median, 60.93 ms p95) failed and remain hidden from ordinary Spot Mask settings.

## Compiled ROI experiment

`dioptas.model.util.mask_plugins.diamond_roi.DiamondROIDetector` prepares coarse
calibrated angles and diamond bands once, then uses serial portable C without
OpenMP or a GPU. Build with `python setup.py build_ext --inplace`. If the native
extension is absent, construction fails explicitly; there is no slow fallback.

Each frame is discovered afresh:

1. Read all image pixels into 8×8 tile means, excluding user masks, nonfinite
   values and optionally zeros. Smooth the coarse image and estimate background
   with separable sliding extrema. Local high-pass contrast provides the scale.
2. Open away thin appendages and label connected coarse seeds; gate their
   signal-weighted angles against diamond spacings. This never masks entire rings.
3. Examine only bounding windows around accepted seeds at full resolution.
   Fit a clipped local background plane; require a peak above the bright side of
   the window border to reject illumination steps. Verify an 8 px square interior
   above local contrast and 1% of the coarse seed peak excess. This prevents a
   bright narrow reflection broadened by reduction from becoming a broad seed.
4. Seed full-resolution pixels above 5 contrast units, then grow through
   connected support above 0.8 units with a 32 px path limit. Return an owned,
   full-size boolean mask. Masked/invalid/zero pixels cannot be included or crossed.

Defaults: background half-window 128 px, minimum coarse seed area equivalent to
100 pixels, maximum combined full-resolution window work 1,000,000 pixels,
diamond `a=3.567 Å`, ±3% d tolerance. Contrast units are not counting sigmas.
A gap through the core can prevent width confirmation. Sharp/narrow diamond
reflections and background-sized features can be missed. Broad sample peaks in
a diamond band remain ambiguous. These limits are tested, not silently filled.

The wrapper serializes access to reusable scratch storage. Native calls also
reject concurrent reuse of a context. uint16/uint32/int32/float32/float64 and
aligned negative/transposed strides are supported without a full image cast.
An exceeded work cap raises instead of returning a partial mask. A measured
call of **10 ms or more raises without returning its mask**. This post-call
check rejects an over-budget result; it cannot promise operating-system latency.

On this macOS ARM64 machine, 76 original, uncorrected 2048² uint16 P1 frames,
8 calls each (608 calls): full Configuration mask-update path **6.98 ms median,
8.30 ms p95, 9.57 ms maximum**. Detector time within it: **6.47 / 7.78 / 9.03 ms**.
The path includes current image scaling, user-mask handling, cached geometry,
mask allocation and manager updates; it excludes file decoding, plotting and
integration. One-time preparation was **4.20 ms**, separately measured; adding
it to detection can exceed 10 ms. Nonempty masks, corrected floating-point
images, other hardware and settings require their own timing qualification.

Frame 039 `(383,1668)` has 356 missed pixels out of 11,145 in the fixed local
background-excess proxy, versus 1,539 with the original powder mask. All 123
saturated pixels within radius 100 are covered. Across P1, 462/4,703 candidate
centres are masked (104 off-band), versus 4,618 (2,727 off-band) for the original
powder mask. These positions are unindexed; this is not a phase-classification
accuracy score. See the saved report for all masks, settings and timing samples.

## Intended behaviour

The detectors target broad anvil reflections when their
centres are compatible with diamond d-spacings. They combine a spacing prior
with spatial detection; it does not blank complete diamond rings. A sample
reflection overlapping the detected diamond core/halo is deliberately
excluded. For later single-crystal intensity extraction, the whole reflection
should be flagged/rejected if its integration support intersects the diamond
mask. Summing only its surviving pixels does not recover its full intensity.
This branch does not alter the separate single-crystal integration checkout.

The original **Spot Mask** remains the available powder-oriented method.
The prototypes remain callable by benchmark scripts so their scientific
results and rejected performance can be reproduced. Saved GUI captures predate
removal from the plugin registry and do not show a currently available feature.

## Spacing prior and earlier slow spatial algorithm

The cubic diamond reference defaults to a configurable `a = 3.567 Å`, an
approximate ambient value consistent with the measurements reported by
[Yamanaka, Morimoto and Kanda (1994)](https://doi.org/10.1103/PhysRevB.49.9341).
The default is not an EOS prediction for the loaded anvil. The cubic metric,
FCC translations and diamond basis give the allowed spacings. The 200 and
222 reflections are absent in this kinematic model. The implementation is
checked independently against an eight-atom structure-factor calculation.

The ±3% default tolerance applies to the signal-weighted scattering angle of a
connected seed, transformed from d bounds using the calibrated wavelength.
Adjust a/tolerance for anvil strain or calibration offsets. A match increases
plausibility; it does not prove phase identity.

The spatial detector:

1. Estimates a radial median/MAD profile excluding masked, nonfinite and
   optionally exact-zero pixels, interpolating between populated bins.
2. Uses local high-pass contrast and clipped local planes, together with a
   morphological background envelope, to reduce sensitivity to illumination
   gradients and steps. These contrast units are not calibrated counting
   sigmas.
3. Detects seeds above 5 contrast units, opens away thin appendages using an
   8 px interior-radius criterion, and retains at least 100 seed pixels.
4. Applies the diamond-spacing gate to the seed centres, then grows through
   connected support above 0.8 contrast units, limited to 32 px beyond accepted
   seeds. Growth may extend outside the seed's d-spacing band.

All these selection/growth parameters are exposed. The local background
half-window defaults to 128 px and should exceed the feature's wings. There is
no upper component-size rejection. Saturated counts are used as observed lower
bounds, without reconstructing an intensity. The broad path uses NumPy/SciPy
and is independent of the optional C/OpenMP and OpenCV paths used by the
original mask. It is considerably slower than the original mask.

## Pipeline and refresh correction

`ImgModel.load_PIL` flips TIFF rows; user image transforms follow.
`Configuration._update_plugin_masks` passes the current **img_data**, user mask
and calibration geometry into `MaskPluginManager`. This data includes any
active background subtraction, corrections and image factor; it is not always
the raw counts described by the old algorithm's docstring. Both image and mask
are transposed for plotting. Rotation angles and PhaseSmith position detection
are not involved.

Calibration `parameters_changed` now refreshes plugin geometry. Previously,
loading/refining calibration without changing the image could leave an enabled
geometry-aware plugin empty or using stale geometry until the next image event.
A regression test reproduces that loading order and verifies the correction.

Frame changes now pass image and geometry to the manager atomically, avoiding
an obsolete-image computation followed by a second computation on the new frame.
Radian geometry maps use pyFAI's unscaled cached arrays, avoiding two full-size
copies. A regression checks one current-image computation and unchanged angle
values; static geometry plugin caches are also invalidated on geometry changes.

A further real-image check found that existing manual flips/rotations can leave
the cached scattering-angle map stale (488–947 mask-pixel differences in the P1
checks). Materializing corners and explicitly invalidating geometry removed
those differences in that trial. A broader transform/reset investigation did
not pass all cases, so that proposed change was not retained. The P1 benchmark
has no extra transforms and is unaffected. General transformed-detector support
is not established by the synthetic array-transform tests.

## P1 investigation

Local evidence is saved at
`/Users/clemens/Documents/Codex/2026-10-25/dioptas-dynamic-spot-mask/report.html`,
with exact settings, all 76 frame masks/metrics, source hashes and comparison
images. No raw data were modified. The known Fe7C3 structure/cell, `ub.ub`,
reference indexing and other sample runs were not used.

In frame 039, displayed `(383,1668)` corresponds to raw TIFF `(383,379)`.
The supplied calibration gives `d ≈ 0.892802 Å`, near the nominal diamond 400
spacing `0.891750 Å`. The original default mask already covers the saturated
core there; its threshold clips the broad wings. This is not a saturation or
component-size rejection. The original mask also removes many small measured
reflection candidates because that is its purpose in powder integration.

The measured-position CSV provides candidate centres, not diamond/sample
labels. Off-band masking is a selectivity proxy. The local halo evaluation in
the report is a background-excess proxy, not diamond-pixel ground truth.

## Limits

Broad sample peaks in diamond bands, connected powder arcs, shadow boundaries
and merged seeds remain ambiguous. Sample diffraction inside an accepted
diamond footprint is intentionally lost. Narrow diamond spots may fail the
width criterion; strain outside the selected tolerance can fail the prior.
Weak or very extended wings can remain beyond the contrast/reach limit.
Features comparable to the background window, harmonics, multiple diffraction
and defect scattering are not reliably handled. Settings require visual
review. A matching d-spacing alone should never be interpreted as a confirmed
diamond assignment.

Synthetic tests cover broad wings, narrow spots, a radial powder ring,
illumination gradients/steps, invalid values, gaps, large saturated components,
image/geometry flips and rotations, spacing extinctions and overlap exclusion.
The combined shadow/ring test permits removal of the arc attached to the broad
peak while checking that unrelated arcs do not become independent seeds; it
does not assert recovery of overlapped sample intensity. The focused CI workflow
runs the tests on Linux, macOS and Windows.

# Experimental diamond spot masking

This is an opt-in mask plugin, disabled by default, on the
`codex/dynamic-spot-mask` investigation branch. It is not a production diamond
classifier or a change to the experimental PhaseSmith spot finder.

## Intended behaviour

Use **Diamond Spot Mask (experimental)** for broad anvil reflections when their
centres are compatible with diamond d-spacings. It combines a spacing prior
with spatial detection; it does not blank complete diamond rings. A sample
reflection overlapping the detected diamond core/halo is deliberately
excluded. For later single-crystal intensity extraction, the whole reflection
should be flagged/rejected if its integration support intersects the diamond
mask. Summing only its surviving pixels does not recover its full intensity.
This branch does not alter the separate single-crystal integration checkout.

Enable the plugin in Mask mode. Review the overlay, and enable **Use Mask** for
integration. The original **Spot Mask** remains the default powder-oriented
method. Its optional `broad` algorithm is the spatial detector without a
diamond prior; enabling both plugins ORs their masks and can mask additional
sample diffraction.

## Spacing prior and spatial algorithm

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

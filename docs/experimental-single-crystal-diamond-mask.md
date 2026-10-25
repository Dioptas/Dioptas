# Broad diamond exclusions in Single Crystal

The experimental Single Crystal **Detection** tab has an optional **Exclude
broad diamond spots** checkbox. It is off by default. Select a PONI calibration
(or use the prefilled Single Crystal calibration), then review the red mask
overlay before finding spots. The controls expose diamond `a` (default 3.567 Å)
and spacing tolerance (default ±3%). The row-convention checkbox is off for
legacy Dioptas calibrations made on the displayed image; enable it when the
PONI describes original, unflipped TIFF rows. Subsequent image flips/quarter
turns use the same affine geometry translation as Single Crystal indexing.

This checkbox is independent of the general **Use mask** setting. Existing
application masks are included only when that setting is on. Nonfinite values
and the selected zero-padding policy still apply. Diamond masks are derived
from raw counts and recalculated for every frame, including rotation-series
searches. Preview overlays show the exact combined mask used by that frame.

The serial native detector is the measured P1 prototype: coarse full-image
discovery, allowed diamond spacings, local full-resolution width/contrast checks
and connected halo growth. It does not identify phases conclusively. Broad
sample features in diamond bands can be excluded, while weak wings and narrow
diamond reflections can remain. Review is required. No sample cell, reference
indexing or material structure enters mask construction.

The initial preparation uses an immutable affine planar-detector snapshot from
the selected PONI. Non-affine or distorted detector geometries are refused.
Only coarse scattering-angle samples are prepared, avoiding a new full detector
map per frame. Worker scratch is independent of the display cache. Calibration,
row convention, transforms, image shape and masking settings invalidate the
prepared/display caches as appropriate.

A detection call of 10 ms or more raises without returning its mask. A mask
failure aborts the measurement/search; it never silently falls back to unmasked
processing. Geometry preparation, plotting and spot extraction are separate
from the mask time shown in the panel. The 76-frame P1 audit gave unchanged masks
in 304 comparisons, 5.05 ms median / 7.75 ms maximum including mask accounting,
with no rejected calls. This is a measured result on the development machine,
not a scheduling guarantee for other workloads.

Diamond-overlapped intensity is not recoverable by summing surviving pixels:
the adapter removes any measured aperture whose half-open box intersects the
diamond footprint. In a rotation series, any linked track containing such an
observation is rejected in its entirety, and retained observation IDs are
remapped consistently. Source counts and files are unchanged. Exports retain
calibration hashes, the native mask binary hash, exact mask settings, per-frame
timings/pixel counts and overlap-rejection counts. Series results remain
unindexed position candidates rather than integrated rocking intensities.

The development launcher accepts `--diamond-mask` together with `--calibration`
to open directly in the Detection tab with the option enabled. The feature is
confined to the experimental Single Crystal UI, and the original powder Spot
Mask is unchanged.

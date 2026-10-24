Omega-series background subtraction
===================================

In the experimental **Single crystal** mode, open a rotation series and select
**Omega background…**. The tool fits a background independently along the omega
sequence at each detector pixel. It can export the signed corrected frames, as
well as raw, background and corrected sum images. Original files are untouched.

Credit and provenance
---------------------

The application of per-pixel baseline estimation along an omega sequence is
inspired by **Konstantin Glazyrin's background-sc**:
https://gitlab.desy.de/konstantin.glazyrin/background-sc .

Dioptas implements arPLS independently from the equations in Sung-June Baek,
Aaron Park, Young-Jin Ahn and Jaebum Choo, *Analyst* **140** (2015), 250–257,
https://doi.org/10.1039/C4AN01061B . No source code from background-sc or its
Stack Overflow references is copied or translated. There is no background-sc,
CUDA, CuPy or Numba dependency.

Method and conventions
----------------------

For each pixel, let ``y`` contain its recorded intensities in frame order. With
``D`` the unpadded second-difference matrix, each iteration solves

.. math::

   (W + \lambda D^T D)z = Wy.

Starting from unit weights, the next weights are

.. math::

   w_i = \frac{1}{1+\exp[2(d_i-(2s-m))/s]},\qquad d=y-z,

where ``m`` and ``s`` are the population mean and standard deviation of negative
residuals. Stop when the relative L2 weight change is less than the tolerance,
or after the specified number of solves. The returned baseline is the last
solved ``z``; capped fits remain available and are marked in ``unconverged.tif``.

The boundary convention is the natural, truncated ``D.T @ D`` penalty with no
padding, extrapolation or reflection. This differs from background-sc's padded
variants; numerical identity to that program is not claimed. The whole sequence
influences each baseline; there is no finite angular cutoff. At least three
uniformly spaced frame midpoints are required. Increasing and decreasing scans
are supported. Split scans at missing frames or angle-step changes.

For stability, traces are shifted by their first value and scaled by their
maximum absolute difference. Constant traces return themselves. Logistic
arguments are limited to [-40, 40] and weights have a floor of 1e-8. Normalized
negative-residual standard deviation has a floor of 1e-8, allowing the limiting
sharp reweighting for noiseless peaks. Fits with fewer than two negative
residuals, or normalized residuals below 1e-10, stop. These numerical safeguards
are part of the documented Dioptas convention. Calculations use float64;
exports use signed float32. No clipping of negative signal is performed.

Inputs, masks and exports
-------------------------

Use one detector image file per exposure from the existing rotation-series
importer, with confirmed omega bounds. Multi-frame containers require a separate
explicit frame/angle mapping and are refused by this tool. Current detector masks
are snapshotted before processing and mapped back from display coordinates into
the original detector orientation. Image corrections and display transforms are
not applied to exported frames.

Pixels excluded by the mask, or nonfinite in any frame, are excluded throughout
the scan. Optional zero-padding exclusion also excludes a pixel if it is zero in
any frame; enable this only when zero means detector padding. Excluded pixel
values are preserved, with zero subtracted background; ``mask.tif`` records
``1=exclude``. Reapply that mask when analysing exported frames.

Each new result directory contains:

* ``raw_sum.tif``, ``background_sum.tif`` and ``signal_sum.tif``;
* ``mask.tif``, ``iterations.tif`` and ``unconverged.tif`` diagnostic maps;
* optionally, ``frames/frame_NNNNNN.tif`` and angle sidecars;
* ``manifest.json`` with parameters, source paths, decoded-image hashes, source
  headers, original sidecar records, omega bounds, frame numbers, convergence
  diagnostics, credit and separate read/processing/export timings.

Corrected TIFF ImageDescription tags carry source metadata and omega bounds.
The original header is preserved as provenance, not claimed to be a replacement
detector-specific TIFF header. Angle sidecars allow the corrected series to be
reopened. ``Open corrected series`` in the dialog uses the in-memory angle mapping
and reapplies the complete exported mask in the current display orientation.
Cancelled or failed jobs remove their staging directory; an existing output
directory is never overwritten. Progress and cancellation run outside the GUI
thread. Source files and the active series are unchanged until the user opens
the corrected series.

Scientific limits
-----------------

Broad rocking peaks, persistent powder/diffuse signal, densely populated traces
and scan-edge reflections can be partly absorbed into the fitted baseline.
Choose smoothness in relation to angular sampling and inspect representative
profiles before interpreting intensities. The defaults (lambda=10000,
tolerance=0.001, at most 30 iterations) are starting settings, not experimentally
validated universal choices.

Background subtraction retains the original counting noise and introduces
correlations through the estimated baseline. Corrected counts alone must not be
used to infer Poisson uncertainties. Exported frames are suitable for inspecting
and finding positions; quantitative intensity work requires validation against
original counts, a noise model and known reflections. No grain assignment,
Lorentz/polarization correction or intensity deconvolution is performed.

CPU performance and validation
------------------------------

The optional native C extension solves the positive-definite pentadiagonal system
using banded Cholesky factorization, O(frames) per iteration. OpenMP distributes
independent pixel traces across a bounded number of workers (default: at most 8).
Each pixel's arithmetic order is unchanged between thread counts. Without the
extension, an independent SciPy banded solver provides CPU support, with lower
throughput. The GUI identifies which backend is available.

Processing uses 4096-pixel tiles and disk-backed input/output stacks. Temporary
stack space is about 12 bytes per pixel/frame, plus final TIFFs (4 more bytes per
pixel/frame when individual frames are exported). The numerical working set is
bounded by tile size; operating-system file caching can still use substantial RAM.
The whole scan must be read before baseline fitting. Cancellation is checked
between reads, tiles and exports, not during one tile's native call.

Tests compare both solvers against an explicit dense-matrix formulation on
deterministic randomized traces, check flat/linear cases, synthetic peak areas
and centroids, signed export round trips, native orientation, masks, metadata,
thread/tile determinism and cancellation cleanup. These establish implementation
correctness on the tested cases, not intensity accuracy for every real scan.

Run a realistic multi-pixel benchmark from the repository root::

   python -m scripts.benchmark_omega_background --pipeline --output report.json

This measures CPU scaling separately from full TIFF reading, processing and
individual-frame export. All pixels have noise and 10% contain a narrow peak.
Use ``--real-seed /path/to/frame_003.tif`` to time a measured scan with confirmed
sidecar angles. Temporary outputs are removed after timing; only the requested
JSON report persists. See ``docs/omega-background-performance.md`` for measured
results and their hardware/workload context.

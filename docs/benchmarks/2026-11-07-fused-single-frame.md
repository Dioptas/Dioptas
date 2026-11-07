# Qt single-frame fused block-decoding comparison

Historical reread prototype, superseded by the [combined one-decode Qt path](2026-11-07-combined-hdf5.md).

Fused block decoding processes independent portions of one HDF5 frame on eight
cores and integrates them with shared float64 weights and private histograms.
The Qt chooser is restricted to fixed-mask, uncorrected/untransformed single-frame
pattern tasks with supported Bitshuffle/LZ4 HDF5 layout. Dynamic masks, spread
statistics, CSR selection, batch/maps, unsupported layouts and missing native
adapters retain their existing paths. Dataset selection is explicit; no detector
brand or file extension is used as proof of eligibility.

## Measured Qt timings

Both paths use the same Eiger 9M data, 2000 bins, polarization 0.965, pixel splitting,
effective fixed mask and float64 arithmetic. The current array kernel uses eight
Rayon threads; the adapter uses eight block workers. Twelve evenly spaced images
are processed in three passes per error setting, rotating backend order, on one
persistent dedicated worker thread. Results are compared outside timing.

| Median (ms) | Intensity | With Poisson errors |
| --- | ---: | ---: |
| Display-image loading | 47.99 | 47.93 |
| Task snapshot | 3.40 | 3.29 |
| Current array worker | 6.52 | 7.40 |
| Fused reread worker | 10.51 | 11.11 |
| Load + snapshot + current worker | 57.86 | 58.62 |
| Load + snapshot + fused worker | 61.97 | 62.43 |

**This is not a Qt speedup.** Qt has already decoded a complete image for display.
Its current worker integrates that resident array. Fused rereading adds another
read/decode and checks every count against the immutable task image. A future
combined display-load/integration operation could avoid duplicate decoding, but
that operation is not implemented here.

The native compressed-input comparison remains valid: 16.73 to 5.38 ms for
intensity and 17.31 to 6.09 ms with Poisson errors on eight cores. Both native paths
started from compressed data. See the maintained
[dioptrin-io report](https://dioptrin-io.readthedocs.io/en/latest/benchmarks/2026-11-07-fused-fixed/README.html).

Qt worker timing includes Python/backend reconciliation, source and count checks,
fused-path reading/decompression, thread launch, merge, normalization and result
conversion. GUI painting, plot application and the Qt debounce are excluded.
Combined rows sum measured stages; they are not GUI FPS measurements. OS cache
is warm because the display loader reads each image first. Other desktop apps
were active. Cold compute with lookup preparation was 0.875 s (current) and
0.780 s (fused), reported separately. The largest scaled intensity difference
was 1.30e-15; all Poisson outputs also met the float64 comparison tolerance.

[Raw timings](2026-11-07-fused-single-frame.json) and
[source/build provenance](2026-11-07-fused-single-frame-provenance.json) accompany
`scripts/benchmark_fused_single_frame.py`. The 5.7 GB data file stays outside Git.
The bridge validates source identity before/after execution and compares decoded
counts exactly with captured bottom-up pixels. Pixel edits use array fallback;
source changes or decoder failures propagate without a partial result.

The optional source adapter is in `dioptrin-io/python-fused` and depends on
Dioptrin fixed-plan commit `72e9b72`. Existing published wheels do not acquire
this capability from the Qt chooser alone. No packages are published and no
batch/map, dynamic-mask, display-loading or 2D-cake algorithms are changed.

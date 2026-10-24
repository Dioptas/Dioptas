# CPU omega-background measurements

Measured on 24 October 2026 on an Apple M4 Pro, 14 logical CPUs, 48 GiB RAM,
macOS 26.6.2, Python 3.13.5, NumPy 2.4.1, SciPy 1.16.3. Native C extension built
with Homebrew LLVM and OpenMP, `-O3`; no fast-math and no GPU. These are local
wall-clock measurements with other work possible on the machine, not guaranteed
throughput on other systems. These measurements describe Dioptas itself;
a subsequent [direct comparison with background-sc](omega-background-cpu-comparison.md)
measures the unchanged upstream CPU arPLS function separately.

All measurements use λ=10000, relative weight tolerance=0.001, at most 30 solves
per pixel, 4096-pixel tiles, float64 computation and signed float32 TIFF export.

## CPU scaling

The deterministic synthetic workload has 180 frames at 512 × 512 pixels. All
262,144 pixel traces have noise and a gently varying background; 10% have a
narrow reflection. Seed: 20261024. Timing includes validation, tile copies,
baseline fitting, diagnostics and a baseline checksum; it excludes file I/O.
Each result is the median of three runs after a small OpenMP warm-up.

| CPU workers | Median processing | Range of three runs | Relative to one worker |
|---|---:|---:|---:|
| 1 | 5.153 s | 4.963–5.178 s | 1.00× |
| 4 | 1.540 s | 1.540–1.552 s | 3.35× |
| 8 | 0.866 s | 0.851–0.930 s | 5.95× |

All worker counts returned identical checksums, iteration counts and convergence
counts. Unit tests additionally compare whole output arrays exactly between
worker counts. Mean solves per pixel: 5.97; 729 pixels (0.28%) reached the cap.

On a 256-trace subset of the same data, the independent SciPy reference took
0.0380 s and the serial native path took 0.00552 s. Maximum absolute baseline
difference was 1.38e-10 counts. This small reference comparison is a correctness
check and indicative timing, not a whole-stack SciPy benchmark.

## Complete reading, processing and individual-frame export

| Workload | Read/stage | Fit and accumulate | Export | Total |
|---|---:|---:|---:|---:|
| Synthetic, 180 × 512 × 512 | 0.616 s | 1.300 s | 0.322 s | **2.238 s** |
| Measured Fe7C3_P2_C2_D1s, 76 × 2048 × 2048 | 3.043 s | 12.957 s | 1.765 s | **17.766 s** |

Both use 8 workers and export every corrected frame, summary maps,
angle sidecars, source-header provenance and a JSON manifest. Source image
hashing is included in reading. The synthetic TIFF sources are float32, so tiny
rounding differences from the float64 compute-only workload change two cap flags.
The full pipeline stages disk-backed stacks, adding data-movement overhead to
the compute-only timing. Writes close the files but do not request a durable
`fsync`; disk and OS caching affect these times. Final manifest serialization,
directory publication and temporary-directory cleanup are outside the timers.

For the measured scan, zero-padding exclusion was enabled. Of 4,194,304 detector
pixels, 900,837 (21.5%) were excluded because a value was zero/nonfinite somewhere
in the scan; excluded values were retained unchanged and marked in the output
mask. The remaining 3,293,467 traces averaged 9.69 solves. 249,020 (7.56% of
processed pixels) reached the iteration cap. This larger cap fraction is a reason
to inspect baseline fits and adjust settings; it is not concealed or treated as
validated intensity recovery. The output occupied about 1.36 GB. No original data
were modified and benchmark output frames were removed after measurement.

The measured run demonstrates completion and speed on actual detector data.
Scientific validation here is limited to the synthetic narrow-peak area/centroid
tests and numerical reference comparisons. Peak-integral accuracy on Fe7C3 has
not been established by these timings.

## Reproduce

From the single-crystal checkout, with the native extension installed:

```sh
python -m scripts.benchmark_omega_background --pipeline --output report.json
```

To add a measured numbered scan with confirmed `omega0`/`omegaR` sidecars:

```sh
python -m scripts.benchmark_omega_background --pipeline \
  --real-seed /path/to/sample_003.tif --exclude-zero-padding --output report.json
```

Omit `--exclude-zero-padding` when zeros are valid recorded counts. The measured
scan above used `exclude_zero_padding=True` through the public API.

Full raw timing samples and convergence counts are retained in
[`omega-background-benchmark.json`](omega-background-benchmark.json).

## Validation status

The 45 new numerical, export and GUI tests pass. The combined omega-background
and existing single-crystal/rotation-series checks passed 60 tests. Native
extension build, critical lint and whitespace checks also passed.

The full local suite returned **1914 passed, 15 skipped, 9 subtests passed and
one failure**. The failure is the existing AppImage launcher test when a prior
`test_MainController::test_load_with_configuration` leaves a global
`subprocess.Popen = MagicMock()` in place. Running those two existing tests in
that order reproduces the failure; the launcher test alone passes. This unrelated
test isolation problem was not changed with the numerical feature.

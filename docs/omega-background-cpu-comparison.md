# Direct comparison with background-sc's CPU arPLS

Measured on 24 October 2026 on the same Apple M4 Pro as the original Dioptas
benchmark. This comparison calls **Konstantin Glazyrin's unchanged published
CPU arPLS function**, alongside the independent Dioptas native CPU solver.

## Reliable measured result

Both use **one CPU worker**, the same 8192 measured detector-pixel traces from
the 76-frame Fe7C3_P2_C2_D1s scan, identical five-value edge padding at each end,
λ=300, tolerance=1e-6 and exactly six linear solves. Three repeats followed
a small warm-up. Inputs were deterministic random selections (seed 20261024)
from a 512 × 512 crop, native detector rows [512,1024), columns [768,1280).
Pixels zero/nonfinite in any frame were excluded before selection.

| Implementation | Median time | Range of three runs |
|---|---:|---:|
| background-sc CPU `baseline_arPLS` | **5.415 s** | 5.265–5.441 s |
| Dioptas native CPU `arpls_rows`, one worker | **0.08973 s** | 0.08570–0.09049 s |

The ratio of medians is **60.35×**. Individual paired ratios were 58.68–63.19×.
This is baseline-computation speed, excluding reading, process startup and
writing. The upstream function's ordinary per-trace Python invocation and sparse
matrix assembly remain included. Dioptas processes contiguous traces in native
code with banded Cholesky factorization and reuses per-worker workspace.

The source's `niter=5` allows six solves (`count > niter`), so Dioptas was given
`max_iterations=6`. All sampled traces used all six solves in both implementations;
this is a matched fixed-work benchmark, not a claim that those settings converge.

Both returned finite baselines. They are not bit-identical: the RMS difference
was 0.00232 counts and the maximum difference 0.211 counts over the padded arrays.
The source uses float32 inputs/sparse matrices; Dioptas uses float64 computation
and documented safeguards. This difference is not evidence of superior intensity
accuracy. The Dioptas production tool uses natural unpadded boundaries; identical
edge padding here was an explicit benchmark input control.

## Limits of the complete-application comparison

A small 76 × 128 × 128 unmodified upstream application run completed in 2.966 s
from its internal timer, using eight workers and summed-image output. Its
processing interval was 2.890 s. This crop run served as an invocation check.

The full 76 × 2048 × 2048 upstream run was **externally suspended** partway
through: all eight workers were observed in the OS stopped state. A subsequent
76 × 512 × 512 parallel application run was also suspended. Both were terminated
and their elapsed times are invalid; **no full-application speedup is inferred
from them**. This is an execution-environment interruption, not an established
background-sc numerical or application defect.

For context, uninterrupted Dioptas runs on the full scan with the same short
six-solve configuration took 9.020 s for summed output or 9.850 s including all
individual corrected frames. They averaged 5.9994 solves per processed pixel,
and 3,281,794/3,293,467 processed pixels reached the cap. These settings are for
matching the upstream workload, not recommended for quantitative use. The
previous **17.77 s** Dioptas full-scan timing used its different default settings
(λ=10000, tolerance=0.001, up to 30 solves); do not compare it as identical work.

The NVIDIA GPU version was not benchmarked: this machine has no NVIDIA GPU.
The 60× result must not be applied to that implementation or interpreted as
a 60× complete file-to-file processing speedup.

## Source and reproducibility

Upstream source: [CPU script at commit 43e7aef6](https://gitlab.desy.de/konstantin.glazyrin/background-sc/-/blob/43e7aef63123e6ce893f6c67c276870ec18adae6/source/v0.1.0/background_subtract_sc.py).
Its directory is named v0.1.0; its internal version string is 0.0.2.

* Git blob SHA-1: `ea602e11552f58db89369273c1bd40e926fd5132`
* File SHA-256: `8be405e6a1b0fcecb0dd423723c3958368fa718337d1bee9f26a829b59f3a076`
* Python 3.13.5, NumPy 2.4.1, SciPy 1.16.3; native extension `-O3`, no fast-math.

The original script was imported only in an external benchmark environment.
No upstream source or runtime dependency was added to Dioptas. Its
`memory_profiler` import was provided in a temporary benchmark-only directory.

Download and review that exact upstream file, then run from the checkout with
its optional imports available in the benchmark environment:

```sh
python -m scripts.compare_omega_arpls_cpu \
  --upstream-script /path/to/background_subtract_sc.py \
  --seed-frame /path/to/Fe7C3_P2_C2_D1s_003.tif \
  --output comparison.json
```

The source detector files are only read. The comparison script records the
upstream file hash, settings, timings, convergence counts and numerical differences.
Raw measurements: [omega-background-cpu-comparison.json](omega-background-cpu-comparison.json).

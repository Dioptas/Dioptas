# Detector-image phase-line updates

Pressure, temperature, lattice and EoS edits previously rebuilt the full detector
2θ field on every `integration_phase_guides` request. Each reflection then rebuilt
sample-grid strip bounds and rescanned the full detector field for its limits.
This repeated work grows with detector size and reflection count.

The native session now caches the existing display sample grid, its full-field
limits and conservative strip bounds for one geometry and image shape. It retains
only sampled angles, rather than a full detector-sized array. Exact-angle contours
from the preceding request are reused for unchanged reflections; only the current
request's targets are kept, so pressure scrubbing cannot grow a contour history.
Style, phase identity and reflection metadata are assembled on every request.
Geometry, detector/distortion or shape changes replace the cache.

When at least 32 changed contour levels cross the image, the session now traces
them together. One row-major traversal reads each sampled cell's corner angles,
then a sorted level lookup selects only the reflections crossing that cell.
Compact contour graphs avoid individual tree/neighbor allocations; independent
path assembly uses the selected processing-worker pool. Sorted start IDs and
ordered collection retain the exact preceding path order. Smaller updates keep
the existing strip-indexed lookup. The final guide array is moved into its reply,
removing an extra deep copy of every coordinate.

The sample grid, interpolation, point order, half-pixel convention and intensity
styling are unchanged. Integration, phase/EoS calculations and detector image
resolution are unchanged.

## Measurements (2026-11-11)

Development-profile processor builds, local macOS, native stdio round trips
including JSON serialization, transfer and Node parsing. Each warm figure is the
median of ten pressure edits (Mo: 1, 2, 3, 4, 5, 4, 3, 2, 1, 0 GPa), after a first
request at 0 GPa. The original three-phase runs also load Au and Pt and inherit
the application's default **Apply to all**, so all three phases change pressure.
Both builds use the same fixture, settings and pressure sequence. The large
detector is a synthetic 3072 × 3072 image with tilted custom geometry, not a
measured detector exposure.

| Detector | Phases | Before (ms) | After (ms) | Speedup |
|---|---:|---:|---:|---:|
| Pilatus1M fixture (1043 × 981) | 1 | 16.89 | 5.49 | 3.1× |
| Pilatus1M fixture | 3 | 30.99 | 13.28 | 2.3× |
| Synthetic tilted 3072 × 3072 | 1 | 110.60 | 7.22 | 15.3× |
| Synthetic tilted 3072 × 3072 | 3 | 164.96 | 20.04 | 8.2× |

First-request times after the change were 14.59/23.41 ms on Pilatus and
82.97/97.60 ms on the large detector (one/three phases). That request constructs
the geometry cache. These are guide-command timings, not physical screen latency
or total phase-edit latency; GUI scheduling and drawing add their own work.

Every before/after guide response had the same SHA-256 hash of its full JSON line
data, for all 11 pressure states in each of the four cases.

### Shared contour tracing: 20 phases

The following comparison measures the additional improvement over the initial
caching implementation, using 20 Mo/Au/Pt-derived test phases with distinct
lattice constants. One-phase runs retain distinct pressures for the other 19
phases; Apply-to-all runs change all 20 together. The benchmark explicitly sets
the edit scope, rather than inheriting the application's default. These replace
the earlier conversational scaling table, whose edit scope was mislabeled and
whose repeated materials did not exercise 20 distinct moving contour sets.

Two processors were invoked back to back for every pressure state, alternating
their order to limit effects from other builds running on the machine. The table
gives medians of ten warm guide requests per version; timings include native
serialization, transfer and parsing, and exclude phase-edit calculation and screen
drawing. Full guide data matched exactly for every paired request.

| Detector | Edit scope | Previous cache (ms) | Shared tracing (ms) |
|---|---|---:|---:|
| Pilatus1M | One phase | 29.39 | 20.69 |
| Pilatus1M | Apply to all 20 | 87.87 | 30.89 |
| Synthetic tilted 3072 × 3072 | One phase | 41.31 | 31.73 |
| Synthetic tilted 3072 × 3072 | Apply to all 20 | 133.11 | 45.20 |

The largest gain is approximately 2.9× for all phases moving together. More
visible contours still require more line data and drawing work. This does not
make update latency independent of reflection count.

### Binary coordinates and retained drawing

The native state now advertises `supportsBinaryPhaseGuides`. The UI requests
`integration_phase_guides` with `{ "binary": true }` only when supported; the
default JSON response remains available for compatibility/reference clients.
Each visible phase owns one immutable `xy-f64le` coordinate buffer. Paths refer
to slices with `count`, `offset` and `length`; metadata retains the same phase,
reflection, color, width, opacity and 2θ fields. The existing content-addressed
binary channel omits buffers already retained by that window. A phase's buffer
is rebuilt only when its ordered angles or detector geometry change. No float32
conversion or curve simplification is used.

`RasterTransfer` validates and attaches the buffers without constructing nested
point pairs. Detector-window snapshots carry these same buffers separately from
their metadata and retain their existing aggregate byte limit. Native path
objects are cached by immutable coordinates and view projection. One combined
transparent layer handles unchanged redraws; up to eight phase groups reuse
unchanged sublayers during edits when their combined backing stores fit 64 MiB.
Larger views retain one combined layer. PNG exports stroke vector paths directly
at the requested resolution, rather than using interactive raster caches.

Paired JSON/binary native stdio measurements with 20 distinct test phases:

| Detector | Edit scope | JSON (ms) | Binary (ms) | JSON bytes | Binary bytes |
|---|---|---:|---:|---:|---:|
| Pilatus1M | One phase | 15.20 | 5.14 | 2,479,418 | 116,866 |
| Pilatus1M | Apply to all 20 | 24.70 | 16.07 | 2,526,856 | 1,597,714 |
| Synthetic tilted 3072 × 3072 | One phase | 23.47 | 6.49 | 3,916,794 | 119,934 |
| Synthetic tilted 3072 × 3072 | Apply to all 20 | 38.62 | 24.49 | 3,940,822 | 2,367,468 |

These are medians of ten warm guide requests, with the two processors called
back to back in alternating order. The tests use the same phase/pressure setup
as the shared-tracing comparison. Timings exclude phase edits and screen drawing.
Decoded metadata and every coordinate matched the JSON reference exactly.

The headless Canvas2D test uses 20 phases/259 visible contours on an 800 × 520
CSS-pixel canvas. Median paint time while editing one phase fell from 17.8 to
3.3 ms in Chromium and 7 to 2 ms in WebKit. Unchanged redraws fell from 17.3/5 ms
to under 1 ms in both browsers (WebKit's timer rounded to zero). These measure
canvas drawing plus a readback to flush work, not physical screen latency.
Only 5,435 new path segments from the edited phase were built; unchanged phases
kept their paths. Metadata-only refreshes and style changes built no new paths.

Pixel comparisons cover normal/zoomed views and DPR 1, 2 and 2.56. Interactive
group compositing introduces small 8-bit antialiasing-rounding differences:
maximum 6/255 in Chromium and 4/255 in WebKit, with mean channel error below
0.14/255 across the canvas. Direct vector-path export matched the preceding
renderer's pixels exactly in both browsers at 2048-pixel export width.

### All-phase updates: parallel angle bands

Changed levels are now partitioned into narrow sorted angle bands, processed by
the existing selected worker pool. Bands reuse the sampled field and strip
bounds, skip strips outside their full level range, and share cell reads within
each band. Graph insertion stays row-major and results return to the original
reflection order. Exact paths also match with one and four workers. Small
updates retain the preceding serial strip lookup.

When every displayed phase changes its coordinate buffer, the renderer paints
the combined layer directly; rebuilding group bitmaps cannot provide reuse in
that case. Partial edits retain group caching. Drawing this all-phase case still
takes roughly 8–9 ms in headless WebKit; the main additional gain is native
contour generation.

Paired all-phase binary measurements (20 test phases; ten warm guide calls,
alternating processor order, with other test jobs finished):

| Detector | Before bands (ms) | After bands (ms) |
|---|---:|---:|
| Pilatus1M | 15.57 | 9.38 |
| Synthetic tilted 3072 × 3072 | 24.16 | 12.46 |

All guide metadata and content-addressed coordinate buffer identities matched
the preceding processor for every pressure state. These are generation/transfer
times, excluding pressure calculation, GUI scheduling and physical display
latency. Adding the previously measured 5–6 ms pressure update and 8–9 ms WebKit
painting gives an estimated 23/27 ms of benchmark stages (Pilatus/large detector),
rather than the prior 29/38 ms estimate; these sums are not click-to-screen
measurements.

## Verification

- Rust contour tests compare cached sampling against the existing algorithm
  across dimensions, sample steps, saddles, nonfinite pixels and boundary values.
- The native phase-guide test compares all line data against the previous
  algorithm after pressure, temperature, lattice, bulk-modulus, color, Undo/Redo,
  geometry and shape changes, and checks bounded contour-cache size.
- Batched-level parity covers unsorted/duplicate levels, saddles, nonfinite
  pixels and several sampling steps. Multi-phase native checks cover individual
  and shared condition edits, phase visibility and identical-angle reuse.
- Isolated Rust library suite: 75 passed, two external-image tests ignored.
- Native binary tests check every coordinate bit against JSON, retained buffer
  identity, zero retransmission for unchanged phases and one new buffer after
  a one-phase pressure edit. Browser unit tests cover cache reuse, invalid
  slices, float64 values and detached binary snapshots.
- Frontend unit suite: 116 passed. Native host suite: 32 passed, including
  many-phase snapshot retention and atomic rejection of invalid ranges.
- Headless Chromium and WebKit checks edit pressure through the phase table,
  confirm changed detector-canvas paths with ten distinct phases moving together,
  stay in Image mode, undock/dock with the phase lines retained, and report no
  page errors. They decode real native packets through `RasterTransfer`.
  Frontend production build passes.

Reproduce from the repository root:

```sh
cargo test --locked --manifest-path backend/Cargo.toml --lib
npm run build
node scripts/phase_guides_smoke.mjs
DIOPTAS_GUIDE_SMOKE_PHASES=10 node scripts/phase_guides_smoke.mjs
node scripts/phase_guides_rendering.mjs
node scripts/phase_guides_rendering.mjs --all
node scripts/phase_guides_benchmark.mjs [processor-executable] [--large] [--single] [--phases=20] [--all] [--binary]
```

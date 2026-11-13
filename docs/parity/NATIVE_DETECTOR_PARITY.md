# Native detector geometry qualification

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `../architecture/REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](../architecture/REFERENCE_DATA.md) for retained fixtures and current checks.

React/Tauri now defaults to this Rust processor with Dioptrin. It never invokes
pyFAI or Python. The Python comparison launcher remains explicitly selectable.
See the [Python-removal audit](../history/PYTHON_REMOVAL_AUDIT.md) for distribution and compatibility work.

## Ownership and supported behavior

The Dioptas migration target is its existing flat-detector workflow: detector
identification, pixel sizes, orientations, distortion splines and Fit2D geometry.
Curved geometry is a shared-library capability and a reference-test case, not a
new Dioptas workflow or a requirement for completing this migration stage.

Physical detector definitions, orientations, cubic Fit2D splines, coordinate
evaluation and Fit2D/PONI conversion belong to **Dioptrin**. Image decoding and
stored acquisition metadata belong to **dioptrin-io**. Decoding never resamples,
flips or distortion-corrects original samples. NeXus transport and the Dioptas
bottom-up/PONI file-row conversion are application boundary responsibilities.

Dioptrin now owns a frozen pyFAI 2026.9.0 catalogue, including the represented factory configuration options: 109 identities/alias sets,
105 supported quadrilateral models and four explicitly unavailable Pixirad
hexagonal models. It retains physical pitches, maximum dimensions, built-in
masks, nonuniform edges, module gaps and supported curved corner coordinates.
Perkin's default binning and manufacturer Rayonix pitch tables are handled.
The catalogue does not require pyFAI at build time or runtime.
Factory pitches and current image pitches remain distinct: for example,
Perkin's default 2048-square frame uses 200 µm pixels over a 100 µm physical
grid. PONI imports resolve these against the loaded image once, without applying
binning twice. An ambiguous Custom-detector shape mismatch is rejected rather
than interpreted as a crop or binning automatically.

Existing detector, NeXus definition, spline load/reset, manual geometry,
Calibrate/Refine and Undo/Redo commands retain their controls. An orientation
selector exposes pyFAI orientations 1–4 (0 is admitted as unspecified). The
physical model is shared by calibration residuals/Jacobians, bootstrap centres,
automatic ring refinement, contours, integration/cake LUTs and normalization,
linked readouts, phase guides, and Spot/radial masks. Module gaps have independent
pixel corners; regular detectors keep the shared-grid/vectorized fast path.

First image loading attempts identification once per fresh configuration:

- Explicit CBF/Pilatus-TIFF or supported NeXus detector identity takes precedence.
- Dimensions must agree with the model; stored pitches, when present, must also agree.
- Without identity, an exact unique shape/pitch match can select a model.
- Ambiguous shapes retain Custom and list candidates. An explicit detector,
  Custom, loaded geometry or project state takes precedence over identification.

The image's typed counts and stored orientation remain unchanged. Detector masks
are separate from editable user/plugin masks and remain active when the user
mask is disabled. Detector masks and interactive geometry are cached; unchanged
definitions retain the existing warm integration plans and combined HDF5 path.

## Geometry and persistence

Manual pyFAI geometry remains SI/radians. Fit2D uses millimetres, pixels,
degrees and micrometre pitches; the command's wavelength remains SI, as before.
Fit2D cannot retain an arbitrary independent PONI rot3; conversion follows the
existing pyFAI convention. Changing pitches defined by a spline, corner map or
manufacturer binning table requires resetting to Custom.

PONI v2 files with an explicit orientation receive the same vertical convention
conversion as Qt. Legacy PONI and v2 configurations lacking orientation keep
their established row convention. Spline coefficients are parsed/evaluated in
Rust; a filename alone is never treated as an applied correction in the native
application. Solid-angle spline finite differences and nonplanar normal indexing
follow the existing pyFAI conventions, including their image-index ordering.

Format-2 `.dio` files own the full detector definition and spline text per
configuration. Large NeXus corner arrays use content-addressed HDF5 payloads;
configuration history/reset snapshots retain their original detector. Reloading
does not need original detector/spline files. Standard Qt fields are retained
alongside the native extension.

PONI saves create spline/NeXus companion assets as needed. Assets precede the
atomic PONI update. Absolute resource paths preserve pyFAI's existing loading
behavior; the native importer can rebase moved absolute assets beside the PONI.
Keep companion assets with the calibration. NeXus exports include pyFAI's
required float32 `pixel_corners`, a native float64 extension, and the original
model for permuted splines, preserving exact native round trips. `.dio` retains full precision independently of these companion files.

## Shared dependency checkout

Dioptrin is pinned to `5273868599151eb536ddccca56c7fd80437a0754`, on the local
`codex/detector-geometry` branch. This commit has **not been pushed or released**.
The current workspace's Cargo cache contains it; a clean machine/CI needs that
commit published to the configured Git origin, or an explicit local-source fetch.
No absolute path dependency is committed. With a checkout containing that commit:

```sh
DIOPTRIN_CHECKOUT=/absolute/path/to/Dioptrin
CARGO_NET_GIT_FETCH_WITH_CLI=true GIT_CONFIG_COUNT=1 \
  GIT_CONFIG_KEY_0="url.file://${DIOPTRIN_CHECKOUT}.insteadOf" \
  GIT_CONFIG_VALUE_0=https://github.com/CPrescher/Dioptrin \
  cargo build --locked --manifest-path backend/Cargo.toml
```

This command redirects only that invocation's Git fetch; it does not alter Git
configuration or select a different revision. Once the commit is published,
normal builds need no redirect. Native executable/installer distribution remains
separate from this source migration.

## Verification

- Dioptrin's pre-existing 179 unit tests, plus detector reference tests covering
  all 105 supported catalogue models, full mask SHA-256 comparisons, real Fit2D
  spline samples, Fit2D conversion, orientation/permutation and nonuniform fitting.
- Backend regression suite (45 tests) including new tests for first-load identity,
  ambiguity/manual override, Fit2D/orientation undo, NeXus masks, transformations,
  owned project resources and fail-atomic invalid geometry.
- `scripts/native_detector_parity.py`: 12 independent pyFAI reference cases
  (spline, nonuniform flat and curved NeXus; orientations 1–4), calibrated pixel
  angles, known corrected constant intensities, exported PONI interoperability,
  project restoration without source definitions and unchanged warm-plan counts.
  The Rust child runs with Python and PATH unavailable.
- Headless Chromium and WebKit exercise the 109-model selector, orientation
  Undo/Redo and existing Fit2D form against the real Rust processor. Screenshots
  and receipts are in ignored `artifacts/native-detectors/`.

Catalogue position tolerance is 1e-7 m for float32-derived physical maps. The
real spline comparison allows 1e-5 pixel against pyFAI's float32 evaluator;
native evaluation uses float64 arithmetic over the reference float32 coefficients.
The 12 application fixtures have a maximum angle difference of 4.43e-9 degrees.
These are regression fixtures, not a detector-wide accuracy certification.

## Explicit limits and next work

- Orientations 5–8 and six-corner Pixirad integration are unavailable, as in the
  exercised pyFAI detector implementation. They are never approximated as regular pixels.
- Legacy Qt projects with transformed detectors that lack an owned physical model remain unqualified and fail explicitly. Native projects own that mapping and support these combinations.
- Crops/unknown binning and nondefault manufacturer geometry options are rejected
  when their mapping cannot be determined. The frozen named catalogue represents
  the qualified factory definitions; an arbitrary pyFAI detector configuration
  is not a supported API merely because its class name appears in the list.
- NeXus files embedding flatfield/darkcurrent corrections need their intrinsic
  correction pipeline ported; they currently fail explicitly. Standalone image
  correction controls remain available. Triangle/hexagonal corner arrays and
  sensor/parallax parameters are not silently discarded.
- NeXus corners are bounded to 64 million coordinate values; image/session limits
  and integer-binning checks also apply. Invalid/missing resources roll back the session.
- Broad real-detector calibration studies, arbitrary Python extensions, installer
  bundling/notices and Windows/Linux native qualification remain separate work.

The shared Dioptrin change is maintained in its own Git worktree and pinned by
the application. No library release or application distribution is made by this stage.

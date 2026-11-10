# Native cylinder and sphere absorption qualification

Cylinder and sphere corrections run in Dioptas's Rust processor, with no Python
runtime or fallback. Dioptrin integrates the corrected counts and independent
pixel variances; sample shape, attenuation lookup, GUI and project ownership
remain in Dioptas. The existing Corrections list contains both shapes. No new
toolbar or window is added.

## Physical model and units

The correction divides each pixel by the mean transmission of uniformly
scattering illuminated material:

```
T(d) = < exp[-mu (L_in + L_out(d))
             - mu_wall (W_in + W_out(d))] > illuminated volume
I_corrected = I / T
V_corrected = V / T²
```

Lengths are in mm, attenuation coefficients in mm⁻¹, angles in degrees. Ray
directions are unit three-dimensional vectors. A ray/quadric intersection
parameter is therefore already a three-dimensional distance. The mean is
normalized by the illuminated volume, so zero attenuation gives unity.

- **Cylinder:** an infinite cylinder, axis tilt measured from vertical and axis
  rotation about vertical (rotation zero tilts toward the incident beam).
  Beam width defines a uniform strip across its circular cross-section,
  perpendicular to the projected incident beam. Zero width is the central
  pencil-beam limit; width at least the diameter illuminates the full
  cross-section. Cylinder ends and axial beam-length effects are excluded.
- **Sphere:** a uniform circular beam footprint centered on the sphere. Zero
  width is the central pencil beam; width at least the diameter illuminates the
  full sphere. Finite footprints average the scattering positions around the
  entire beam axis, not just a single plane.
- **Capillary wall:** optional concentric cylinder shell. A scattered ray
  crosses one wall on entry and one on exit. Only sample scattering is
  modeled; wall scattering and its subtraction are excluded. A nonabsorbing
  sample can still have an absorbing wall. Disabling the wall retains its
  material and numerical drafts for later use.

Sample and wall attenuation each support direct μ or Rust XrayDB formula and
density lookup. Formula mode follows wavelength changes. The same compact
322 KiB attenuation subset, energy limits and project fingerprint documented
in the [correction/uncertainty ledger](NATIVE_CORRECTION_UNCERTAINTY_PARITY.md)
are reused; no additional database is embedded.

## Numerical scope and failure behavior

`backend/src/sample_absorption.rs` computes normalized Gauss–Legendre volume
quadrature (orders 12, 24, 48, 80) and a periodic azimuthal average for finite
sphere footprints. Nine angular probes, and nine projected-direction probes
for a cylinder, estimate quadrature convergence at relative tolerance `2e-5`.
An adaptive linear/bilinear angular table checks every cell midpoint at the
same tolerance. Cylinder interpolation uses angle in the cross-section and
inverse outgoing projected norm; sphere transmission depends only on 2θ.
Sphere grids stop at 1025 nodes, cylinder grids at 257 × 257 nodes.

These are convergence estimates, not a rigorous universal error bound. The
independent reference cases below use local relative acceptance `8e-5`,
without relaxing tolerances of existing correction/reference scripts. Large
optical depths or nearly axial cylinder rays can exceed this numerical scope.
Nonconvergence, zero/nonfinite transmission and cylinder directions parallel
to its infinite axis fail explicitly and atomically. Zero radius is treated as
identity, matching the legacy convention. Invalid parameters, invalid active
materials and cancellation retain the prior science and Undo/Redo state.

One geometry/shape/effective-parameter keyed transmission map per shape is
cached in each configuration. New same-shape images reuse the map and propagate
their own original counting variance. Geometry, image orientation, wavelength
or effective parameter changes invalidate it; masking, binning and display
changes do not alter its physics. Cache bytes participate in existing session
memory accounting. Progress and cancellation are checked during convergence
and table construction. Maps are recomputed from saved parameters on project
open, rather than saved as opaque correction images.

## Intentional differences from the Python reference

The original `dioptas/model/util/ImgCorrection.py` remains unchanged and serves
as a reference only. Three geometric defects are corrected in Rust:

1. The cylinder's original outgoing quadratic root already measures a 3D path;
   dividing by the projected ray norm again overestimates tilted paths.
2. The original shell subtracts inner from outer **full chords** on both entry
   and exit. Each physical ray crosses only one wall on each side. For forward
   pencil transmission Rust gives `exp[-2 mu R - 2 mu_wall wall]` for an untilted
   cylinder; the old implementation gives `exp[-2 mu R - 4 mu_wall wall]`.
3. The original finite-beam sphere samples positions in a single plane, omitting
   the azimuthal average over the circular footprint. Rust integrates it.

Consequently numerical identity with old tilted cylinder, absorbing capillary,
or finite-beam sphere results is not claimed. Pencil sphere values agree with
the high-resolution legacy approximation and exact limiting integrals.

## Projects and workflows

Native format-2 `.dio` files retain active and disabled shape parameters,
sample/wall material selections, derived μ, wall enable state, source pixels,
backgrounds, flat fields, masks, transforms and counting-variance ownership.
`native_desktop.sample_absorption` records model `uniform-footprint-rays-v1`,
footprint definitions and convergence tolerances. Reopening and reintegrating
works without the source image, calibration or correction files.

Legacy format-2 shape parameters load and are recalculated with the corrected
model. An enabled legacy shell is inferred from positive wall thickness and μ.
Opening a project containing an active shape without the native model marker
displays **Recalculated legacy sample absorption using corrected geometry** in
the existing footer. Saving writes the new provenance. Native files also emit
legacy scientific parameters, so the Python reader can load them; its numerical
results still follow its old algorithms. Python rewriting loses native-only
material/draft metadata and the model marker. Reopening that file therefore
recalculates and gives the legacy notice again.

## Reproducible evidence

The existing `CI_rust_desktop.yml` native gates include:

- Rust closed-form tests: sphere forward/backscatter pencil limits, full sphere
  forward volume integral, tilted cylinder forward transmission and exactly two
  capillary wall crossings, cancellation and undefined infinite-axis geometry.
- `backend/tests/functional_flows.rs`: both shapes in 2θ/Q/d through background,
  flat field, mask, ROI, supersampling, rotation, same-shape frame changes,
  exported XYE std, Undo, active/disabled projects, retained disabled-wall μ,
  source deletion and fresh-owner reintegration. Additional cases cover invalid
  edits/cancellation/Redo, corrected Batch/Map std and HDF5 persistence,
  combined detectors and offline project reopening.
- `scripts/native_round_absorption_parity.py`: independent NumPy volume
  quadrature and 3D ray intersections for pencil, partial and full footprints,
  tilted cylinder and shell, wide-angle full illumination at μR=2, sample-zero
  formula capillary, cache reuse with changed original counts, independent
  supersampled sector weights and propagated std, Rust/Python project parameter
  cross-reading/writing and migration notice, and the valid legacy pencil limit.
- `scripts/native_material_parity.py`: 168 independent Python XrayDB comparisons
  across all four sample shapes, six formulas/materials and seven energies,
  including edge-adjacent values; explicit μ and formula modes agree through
  intensity/std. Invalid lookup changes preserve the preceding state.
- `scripts/native_corrections_smoke.mjs`: real Rust-backed headless Chromium and
  WebKit controls, sample/container formula sources, wall enable and thickness,
  project reopening and panel layout at 1440 and 1100 px.
- Relocated packaged processor check: correction calculation, material lookup,
  counting std and project reopening with the source checkout denied and Python
  execution unavailable. No application window is opened.

Receipts and screenshots are under `desktop/artifacts/native-integration`,
`native-corrections`, `ci-native` and `standalone`. A local 1043 × 981 Pilatus
check measured about 0.16 s cylinder and 0.05 s sphere cold calculation, and
0.04 s same-shape image reopen with cached maps; these are development-machine
observations, not cross-platform performance guarantees.

Parameter/lookup uncertainties, sample heterogeneity, off-center illumination,
nonuniform beam profiles, multiple scattering and individual cake-bin std maps
remain outside this model. The native [Plot / Back preview](NATIVE_CORRECTION_PREVIEW_PARITY.md) now
displays the same correction maps used by the actual image, pattern, cake and
series data flows.

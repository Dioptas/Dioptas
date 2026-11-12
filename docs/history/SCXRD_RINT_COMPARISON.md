# MgSiO3: matched PhaseSmith/Dioptas protocol comparison

## Diagnosis

The initial 58.9954% Rint came from a separate, simplified adapter around spot
kernels. It was **not** the complete PhaseSmith workflow. Sharing individual
kernels was insufficient: the adapter used detected-track boxes, different
support/background controls, no moving cell-shadow providers and no learned
profile/family-scale reduction. Presenting that path as the standalone workflow
was incorrect.

Dioptas now executes `phasesmith_workflows::single_crystal::run` for the native
protocol, including individual checkpoints. Structure search uses the same
`search_observations` entry point and protocol strategy. Exploratory summation
remains explicitly separate. New sessions select the protocol workflow; old v1
recipes without a method retain their original summation semantics.

## Frozen inputs and controls

The reference is PhaseSmith commit `e47507f4adf32ea2a137ddf6b735db88f8a67537`, its
actual `validation/enstatite-raw-workflow-v29.json` supplied-Pbca protocol and
registered MgSiO3 raw/PONI files. The protocol is bundled unchanged, inspected
and retained by Dioptas. No source HKL, atomic coordinates, atom counts or vendor
integrated observations enter either numerical worker.

| Input | Identical declared value |
|---|---|
| Raw file SHA256 | `f1c15243075672edc8208f38c032ddb299ec8ea3126d83d283b9f601e4e4de3c` |
| PONI SHA256 | `3379885eab3fa523b0004a47880a85f4e5676dd28099e30a641b541e9436bd4a` |
| Frames | Original indices 2–143 of 144; first two seat frames omitted |
| Acquisition | Zero-frame start −36°, step/exposure 0.5°, spindle (−1,0,0) |
| Orientation | Declared vertical flip exactly once |
| Cell prior | 8.8101, 5.1824, 18.2288 Å; 90°,90°,90° |
| Symmetry / elements | Supplied Pbca #61; Mg, Si, O; no atom counts |
| DAC aperture | Sample-fixed axis (0,0,1) at omega zero; declared 35° half opening |
| Seat mask | Original-count ratio threshold 0.85, 32 px guard, 16 px blocks |
| DAC support | Complete closed exposure and complete 16×16-pixel footprint |
| Integration | Predicted crossings, 7 px spatial radius; zeta-adapted rocking half width up to 4.5°; guarded-plane background |
| Profiles / scaling | Protocol's independent native profile learning, native shape fitting, frame/detector/ray family scaling and equivalent-error floor |
| Polarization / counting | 0.98 along lab fast/y; gain 1, read noise 0 |

The angles and DAC opening are explicit exposed-data assumptions, not independently
measured instrument metadata. The protocol remains a supplied-orthorhombic-metric
workflow. Automatic-symmetry protocols are rejected by this first adapter until
their hypothesis-review flow is supported.

## Causal masking control

The following experiment holds the original tracks, fitted geometry, basis,
counts, apertures and statistic definition fixed, varying only shared masks.
These are diagnostics on the old summation path, not candidate-selection trials.

| Shared masks | Usable observations | Rint |
|---|---:|---:|
| None | 2,131 | 58.9954% |
| DAC only | 1,917 | 60.0436% |
| Seat only | 2,021 | 59.8534% |
| Both | 1,895 | 60.3098% |

The missing masks were a real defect, but adding masks to the old boxes does
not reproduce the standalone reduction. On the **same 3,955 finite-aperture
observations** from the native workflow, aperture/physical correction gives
78.1483% Rint, learned profiles/physical correction 10.0129%, and full native
profile/family scaling 3.8634%. Each uses its corresponding reported uncertainty;
this is an attribution subset, not a production membership change. The complete
native result uses all 4,125 eligible observations.

## Matched result

The original build comparison and subsequent matched-build control give:

| Quantity | Standalone, unoptimized | Standalone, matched optimization | Dioptas |
|---|---:|---:|---:|
| Retained reduction rows | 7,277 | 7,277 | 7,277 |
| Native eligible observations | 4,125 | 4,125 | 4,125 |
| Repeated Pbca/Friedel families | 1,033 | 1,033 | 1,033 |
| Rint | 3.9364926% | 3.9364868% | 3.9364868% |
| Retained MISMATCH warnings | 660 | 660 | 660 |

Rint is independently recomputed on repeated families as
`sum(abs(I - inverse_variance_mean(I))) / sum(abs(I))`, retaining signed counts.
The same definition is used in Dioptas. It is not a structural R1.

All 142 prepared-frame hashes match: an image-flipping discrepancy is ruled out
for this matched scan. HKLs, raw quality flags, finite masks and native-use bits
match exactly. Intensity and sigma are numerically equivalent, not claimed
bitwise equal: all-finite relative L2 differences were 4.23e−7 and 1.19e−8;
on eligible rows they were 1.82e−6 and 3.81e−7. The largest eligible intensity
difference was 0.000385 of reference sigma. Existing PhaseSmith v29/v9 equivalence
gates (relative L2 1e−4, max difference 0.1 sigma, 95th percentile 0.01 sigma)
are unchanged.

The GUI now preserves authoritative native eligibility separately from quality
warnings. It does not drop all nonzero flags. Detected tracks and predicted
crossing identities are distinct in the full observation export.

## Every-stage replay and artifacts

The optional stage archive records both mask providers, detection/linking,
indexing and family holdouts, geometry, predicted crossings, original shoebox
samples/backgrounds/variances, native group flags, teacher membership/profile
bank, physical/empirical factors, intensity, sigma, and final membership.
The standalone audit worktree is detached at the same pinned commit; its only
source changes add exports of DAC masks, group flags and correction factors.
No numerical code or protocol changes are made there. Every earlier trial and
failed result remains preserved.

The original unoptimized standalone build and optimized desktop build matched
all integer/boolean structures and passed the existing intensity/sigma gates.
Their refined geometry differed by at most 2.78e−17 in detector vectors and
1.73e−18 in reciprocal basis; some profile-fit diagnostic columns amplified
these small differences. The generic intermediate-array screen failed for
`raw_profiles` and `parameters`. Those failures remain in
`stage-comparison-02.json`; its limits were not loosened.

A controlled standalone rebuild then matched Dioptas's development optimization
settings (`opt-level = 2` for phasesmith-core, phasesmith-crystallography,
phasesmith-single-crystal and phasesmith-workflows). Its original lockfile and
scientific source/protocol were retained. **All 54 archived arrays are now
byte-exact**, including moving DAC and seat masks, detections, links, indices,
holdouts, refined geometry, predicted crossings, shoebox samples/validity/
variances/backgrounds, teachers, profile bank/diagnostics/shape parameters,
physical and empirical factors, final intensities/uncertainties and eligibility.
Initial PONI geometry was separately checked bit-for-bit against standalone
arithmetic and HDF5 pixel pitches. The complete result is retained in
`stage-comparison-optimized-control.json`; final recipe and fresh-GUI replays are
also retained as `stage-comparison-final-source.json` and
`stage-comparison-reviewed-final.json`; the final observation-view source is
verified again in `stage-comparison-final-observations.json`. A second reviewer independently
recomputed the comparison from the actual archives.

Opening the saved protocol recipe in the final desktop worker reproduces 4,125
eligible observations and Rint 3.9364868%. The matched optimized standalone and
desktop search both recover the same candidate R1 **4.1128354912261904%**,
80 atoms and the native anisotropic strategy (90 refined parameters). Search
stops on `r1_target`; the candidate's refinement terminates at `max_iterations`.
This confirms the exercised native search route, not final refinement convergence.
No wall-clock timing or cross-platform bitwise-equivalence claim follows.

Local large artifacts are outside Git under
`/Users/clemens/ChatGPT/SCXRD Validation/2026-11-12-rint/`; small local logs are
under ignored `artifacts/scxrd-rint-comparison/`. The original standalone
unoptimized run completed reduction but returned no structure candidate within
its wall-clock search budget. Its result remains preserved alongside the
successful optimized control. This report qualifies matched reduction and the
exercised candidate-search path, not final structure correctness or absolute
intensity accuracy. Absorption remains uncorrected.

Reproduce the desktop measured replay with an explicit source directory and a
new output directory:

```sh
DIOPTAS_SCXRD_STEPWISE=1 DIOPTAS_SCXRD_MEASURED_DIR='/path/to/MgSiO3 example' \
  node scripts/scxrd_matched_profiles.mjs /new/external/output
python scripts/scxrd_compare_standalone.py /standalone/output /output /mask-ablation.json /new/comparison.json
python scripts/scxrd_compare_stages.py /standalone-audit/output /output/stages.npz /new/stage-comparison.json
node scripts/scxrd_protocol_gui.mjs /output/matched.scxrd.json /new/gui-output
```

Python here is an independent archive-analysis tool. Both processing workers run
natively with no interpreter dependency or fallback.

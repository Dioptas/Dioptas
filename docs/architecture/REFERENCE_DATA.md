# Reference data and Python cleanup

`develop` contains the Rust/React/Tauri app and its native/headless test suite.
There is no active Python application, comparison processor, pytest suite or
Python numerical-reference CI job. The Qt app and its tests live on `legacy/qt`
at `253d0fda505d4f9b159644050efe2f574ce8a3d9`.

The source immediately before this cleanup is
`a39717a41458129ba9370c849a4121ecdbc6a444` (the exact full revision is recorded in the fixture provenance and
legacy inventory JSON files). That revision also retains the later React/Python
compatibility adapter, which was never part of `legacy/qt`.
Historical parity/benchmark reports describe their measured checkpoints;
their removed Python commands are archival reproduction instructions.

## What stays

- `backend/tests/fixtures/reference-data/`: independent pyFAI full pixel-split
  1D intensity/counting std and 2D cakes across radial units, solid-angle choices
  and azimuth sectors; plate/slab correction maps; two-pass LA Cosmic masks;
  NumPy image levels. `numerical.json` records settings, tolerances, source
  revision/hashes, dependency versions and input hashes. Native-selected bin
  ranges are recorded explicitly, so this fixture does not independently test
  the automatic choice of integration range.
- Existing `batch_background_qt.json`, `dac-qt-reference.json`, HDF5 and mask
  fixtures, consumed by Rust tests. The DAC fixture identifies its source
  branches and the Batch fixture identifies its independent algorithm.
- `tests/data/`: measured detector images, PONI/spline files, masks, CIF/JCPDS
  files and other existing input fixtures required by native tests.
- `resources/`: calibrants and scientific reference tables used by the native
  app. Generated native metadata keeps its original source hashes in
  `backend/resources/`; source files can be recovered at their recorded revisions.
- `legacy_functional_inventory.json` and `legacy_command_inventory.json`:
  frozen coverage identifiers, not executable Python. The coverage gate still
  validates every mapped native/headless test and explicitly scoped boundary.

`backend/tests/integration/frozen_references.rs` checks independent expected outputs in
Rust. Tests never regenerate expected results from the implementation under
test. Fixture updates require an explicit reference-version/settings/provenance
review; a changed result is not accepted just by replacing the expected data.
This is regression coverage for the stated cases, not universal equivalence.

## Test input generation

`npm run test:fixtures` builds `backend/examples/test_fixtures.rs`.
Headless transport/progress tests use this native-only helper for long HDF5
series and NPY inputs. A 384×448 uint16 frame, `100 + 2*column + 3*row`, has a
frozen independent Bitshuffle/LZ4 chunk (`transport-frame.bslz4`, 2048-element
blocks). The helper repeats that chunk using HDF5 direct writes, so tests
exercise the processor decoder without installing an external HDF5 plugin.
This creates input only; it does not calculate expected scientific results.

## Remaining Python tooling

Only `docs/source/conf.py` (Sphinx configuration) and
`installer/macos/signing.py` (native Apple signing/notarization utility) remain.
They are outside scientific processing and the active test suite. Python is
not required by native builds or test gates; documentation builds and signed
macOS releases use these utilities separately.

## Cleanup verification — November 12, 2026

415 native Rust tests, 52 Tauri host tests, 182 frontend tests and 15 native
transport tests pass. The frozen numerical replay passes, as do all-feature
and core-only Clippy checks, frontend compilation, command/coverage audits,
release configuration checks and the exercised headless native workflows.
The bulk Map progress check runs without Python or an external HDF5 plugin.
The complete headless UI gate passes all 49 steps, including companion
windows, background export, WebKit image replacement and native transport.

The pre-existing companion-window readout failure is fixed: docking Map no
longer clears the shared click coordinates sent to the detached detector.
`companion_windows_smoke.mjs` passes 42 checks in each of Chromium and WebKit,
including repeated detector/Batch/Map docking cycles in 2θ and Q. Its Map
canvas assertions now target the embedded Map detector and open the Image
tab when needed, preserving the independent Integration companion behavior.

Documentation migration is deferred. The existing documentation configuration
and native macOS signing utility remain tooling exceptions, not test suites.

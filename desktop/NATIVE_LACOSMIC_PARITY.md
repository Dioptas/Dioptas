# Native LA Cosmic operation

The default Rust processor implements `mask_edit {operation: "cosmic"}`.
React's Mask panel exposes the Qt **Cosmic Removal** action below the morphology
controls. The existing Python desktop command also accepts this button's payload.
The ordinary launcher now uses Rust; native LA Cosmic requires no optional
Dioptrin feature, Python runtime, SciPy or additional native dependency.

## Preserved behavior

The operation adds the detected cosmic-ray hits to the current user mask and
enables use-mask. It is a single mask Undo/Redo step. Existing masks do not exclude
pixels from detection, and the command remains additive when the drawing mode is
Unmask, matching both Qt's `MaskModel.remove_cosmic` and the desktop command.
Dynamic plugin masks retain their own settings and ownership and refresh through
the existing processing pipeline.

Each invocation starts from the current processed scientific f64 image, including
image orientation, backgrounds, flat fields and corrections. It always runs two
detection/cleaning passes. The cleaned plane is temporary input for the second
pass; raw pixels, processed counts, histograms and calibration state are retained.
The resulting user mask participates in Integration/Batch/Map like any other
painted mask, persists per configuration in `.dio`, and is available offline.

The parameters remain fixed, as in the existing one-button workflow:

| Source parameter | Value |
| --- | --- |
| Passes | 2 |
| `gain` | 2.2 |
| `readnoise` | 10 |
| `sigclip` | 3 |
| `sigfrac` | 0.3 |
| `objlim` | 3 |
| `pssl` | 0 |

The adapter follows the bundled `cosmicsimage.lacosmiciteration` + `clean` route.
It does not call `run`/`findsatstars`; the source's optional saturation-star search
is consequently not part of this operation. This is compatibility with the
existing detector-mask action, not a detector-wide classification accuracy claim.

## Numerical boundary and cancellation

The native core retains the replicated 2×2 Laplacian, positive clipping,
axis-ordered rebinning, gain/read-noise model, whole-sample mirror median windows
of 5×5, 3×3 and 7×7, fine-structure rejection and both neighbor growth thresholds.
It evaluates the replicated Laplacian directly without storing four times as many
pixels. Cleaning uses unmasked 5×5 neighbors from the pass's frozen selection,
the conventional mean of two middle values for even neighbor counts, and a cached
median of the original image when no usable local neighbor remains. No saturation
mask or preexisting user/plugin mask is injected into those neighborhoods.

Source plane dimensions retain the native session's 64-million-pixel bound.
NaN/infinite processed input and nonfinite arithmetic intermediates fail before
publication. The native implementation requires finite science rather than relying
on the source rank filter's undefined NaN handling; see
[the SciPy median-filter notes](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.median_filter.html).
Invalid/cancelled operations preserve pixels, products, user/plugin masks, mode
and history, including an existing Redo entry.

Progress retains **Cosmic removal**, two passes, and the existing Cancel mask
processing action. Additional stage metadata identifies the active numerical
step. Cancellation is checked throughout image rows, median windows, neighbor
classification and cleaning. The rare full-image fallback median is one bounded
selection call, checked before and after. The real stdio reader handles progress
and cancellation independently of the scientific worker.

## Reference and checks

The canonical source is this checkout's
`dioptas/model/util/cosmics.py` version 0.4, credited to Malte Tewes (2010) and
based on Pieter van Dokkum's Laplacian algorithm. SHA-256:
`398f3ccca09ea5efc4e3234942f1491f07c97579de2f9a491ec2056b2f84a357`.
The read-only current Qt checkout contains the same file. Command behavior comes
from `dioptas/desktop/mask.py` and `MaskModel.remove_cosmic`; the button grouping
follows `dioptas/widgets/MaskWidget.py`. Those Python/Qt sources were not edited.

From the repository root:

```sh
cargo fmt --manifest-path desktop/backend/Cargo.toml --check
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --all-targets --all-features -- -D warnings
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --all-targets --no-default-features -- -D warnings
cargo test --locked --manifest-path desktop/backend/Cargo.toml --all-features
cargo test --locked --manifest-path desktop/backend/Cargo.toml --no-default-features
.venv/bin/python desktop/scripts/native_lacosmic_parity.py
cargo build --locked --manifest-path desktop/backend/Cargo.toml --all-features
cd desktop
npm test
npm run build
npm run test:native-lacosmic
npm run test:native-lacosmic-transport
```

The reference script can run against either feature variant. Rebuild all features
after no-feature tests before other numerical migration checks, because integration
tests can replace the debug processor executable. Python/NumPy/SciPy/Pillow/h5py
are test references and fixtures only; the native child runs with Python and PATH
unavailable.

Seventeen mask comparisons cover tiny/one-row/one-column images, corners/edges,
isolated hits, clusters/weak neighbors, multiple random backgrounds, negative and
fractional counts, extended bright structure, the measured CeO2 TIFF, and a
rotated/background/flat-corrected plane with a dynamic plugin. Every compared mask
matches exactly; several cases explicitly gain hits only in the second pass.
The measured fixture yields 55,195 first-pass pixels and 26,796 additional
second-pass pixels (81,991 total). These are regression counts for this fixture.

Rust tests additionally cover frozen-neighborhood cleaning, even-count medians,
the global background fallback, one-step additive history, saved calibration
retention, nonfinite-input rejection and cancellation rollback. Project tests
exercise per-configuration/offline mask ownership. Chromium/WebKit click Cosmic
Removal, Undo, Redo and Cancel during the actual second pass; the stdio test
verifies immediate cancellation replies, exact state restoration, stopped progress
and queued cancellation. Receipts/screenshots are under ignored
`desktop/artifacts/native-lacosmic/`. Routine verification stays headless; native
window/dialog and Windows/Linux execution are separate qualification work.

Checkpoint, 2026-11-07: all 38 native tests pass with Dioptrin and all 32 pass
without it; strict Clippy passes in both feature modes. All 17 reference mask
comparisons pass with and without the engine. The new Chromium/WebKit workflows
and real-stdio cancellation checks pass; the WebKit screenshot was inspected.
The frontend build, all 60 JavaScript and 19 Tauri host tests pass. Existing
geometric/orientation and bundled-plugin comparisons and both browser workflows
also pass. No visible user window was opened.

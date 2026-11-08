# Detector combination in the consolidated Rust desktop

The detector-combination interface is included in `codex/rust-desktop`.
The original interface commit `6db5c58d` was merged by `37b7dfdf`; the
scientific commands were ported to `desktop/backend/src/combination.rs`.
The default application uses the Rust processor and compiled Dioptrin crate.
It does not use a Python wheel or fall back to Python or pyFAI for combination.

## Interface

Enable **Settings → General → Multi-detector setups → Show configuration
controls**. This existing preference remains off by default and persists across
restarts. The shared configuration bar supports add, duplicate, rename,
select and remove. Hiding it preserves configurations and the selection.

With two or more configurations, the top-bar configuration controls include the
selected detector's **Factor**, independent **Combine patterns** and **Combine images** switches,
and **Save combined pattern**. These controls remain available across modes.
**Combine images** merges calibrated 2D cakes in common diffraction coordinates.
Factor commits on blur or Enter and scales that
detector's scientific pixels before integration. Images remain independent;
combination produces calibrated patterns/cakes, never a detector-image mosaic.
Each configuration retains its image, calibration, masks, corrections and
scientific coordinates. Detector contrast, palette, linear/log and Auto settings
follow the stable configuration identity. Individual and combined cakes have
separate display settings. Pending scientific drafts prevent configuration changes.

The same bar provides previous/next **File** and **Folder** actions. Configure
them under **Settings → General → Multi-detector setups → Configuration
browsing**. The default scope is **Active configuration**; **All configurations**
advances every detector from its own source, retaining calibration, masks,
corrections and factors. Combined products are recomputed. The bar shows the
current scope. The existing Image panel's individual browsing controls remain
independent of these configuration-bar rules.

File and folder rules independently select a numbered part, counting from the
right, and a positive step size. Number 1 means the last number, 2 the preceding
number, and 0 tries numeric groups from right to left. Folder numbering counts
across the directory path. File browsing respects each configuration's name/time
ordering; time ordering uses the configured step instead of filename numbering.
Folder browsing normally retains the filename. **Filename number with folder**
can additionally advance any selected filename number, using its own step; 0
leaves the filename unchanged. **Use MEC preset** selects all configurations,
automatic folder numbering, and the third filename number with unit steps,
matching the Qt convention. Every rule remains editable after applying the
preset. **Reset browsing** restores active-only browsing and default rules.
Preferences persist across restarts.

Configurations without a matching file remain in place and are reported in the
status notice. An unreadable file or detector-dimension change rolls back the
entire grouped action. A dimension change must first be opened and explicitly
reset for that detector. The active configuration remains selected.

## Native processing

Tauri's default stdio child is `dioptas-processor`. The combination commands
are handled by Rust `Session`; its response identifies both combination products
as **Dioptrin · native Rust**. The native kernels are
`dioptrin::multi::MultiIntegrator::integrate2d_from_slices` with
`MultiNormalization::Absolute`. Signal, normalization and optional variance are
accumulated on the shared grid before division. Pattern integration uses one
azimuth bin of the same native API. Separate prepared pattern and cake plans
retain warm grids, geometry, masks, units, sectors and polarization.

Each configuration supplies its own physical detector geometry, dimensions,
corrected/scaled f64 samples, effective mask and supersampling. The selected
configuration supplies the radial unit/binning, cake resolution, polarization
and azimuth sectors. Coverage spans all participating detectors, including gaps.
Patterns support 2θ, Q and d. Cakes use Q in Q mode and 2θ in 2θ/d mode;
readouts, linked guides and exports follow their actual coordinates.

Combination requires calibrated images in every configuration and solid-angle
correction. Unsupported detector/uncertainty settings fail explicitly and
preserve the preceding scientific state. Combined counting errors accept variances propagated through detector factors,
backgrounds and supported image corrections; see the
[correction/uncertainty ledger](NATIVE_CORRECTION_UNCERTAINTY_PARITY.md). Fractional splitting does not imply bitwise Qt full-split identity,
especially at beam/seam and coverage boundaries.

The Cargo dependency remains pinned to Dioptrin revision
`6ede5d0553811a41ad4511d1f5a50d955eb85156`, which combines physical-detector support
and shared-grid multi-detector integration with validated beam-splitting fixes
and explicit pixel-variance accumulation.
Replacing it with the plain 0.11.0 tag would remove physical-detector support
needed by this desktop. The Python dependency pin belongs to the explicitly
selected compatibility/reference runtime and does not select the native engine.
See [the consolidation record](RUST_DESKTOP_CONSOLIDATION.md) and
[native detector qualification](NATIVE_DETECTOR_PARITY.md).

## Saving and projects

**Save combined pattern** and the ordinary **Save displayed pattern** action
write the displayed combined curve through the native format writer. The latter
also uses the combined curve for the legacy `export_pattern` command while
combination is active. Exported error columns require a qualified sigma array.
Cake PNG/TIFF/TXT/CSV saving and Auto intensity operate on the displayed combined
cake rather than the selected detector's ordinary cake. Native project saves
retain configurations, selected identity, factors, masks, geometry and combination
flags. Reopening recomputes the native result. No authored source image is changed.

## Verification

Run from `desktop/`:

```sh
npm run backend:test
npm run backend:build
npm run build
npm test
npm run test:combination
```

`backend/tests/desktop_consolidation.rs` checks the Rust/Dioptrin identity,
raw-contribution factor ratios, independent masking, combined data/export,
project round trips, unequal image shapes, physical geometry preservation and
Q/d coordinates. It verifies both combined-save routes against the displayed
numerical curve, including normal Save displayed pattern.

`test:combination` runs the real Rust stdio child in headless Chromium and
WebKit with `DIOPTAS_PYTHON=/nonexistent/python` and `PATH=/nonexistent`.
It asserts `runtime=rust`, `engine=dioptrin`, both native combination providers,
actual curves/cakes, factors/export, configuration persistence, independent manual
contrast/Auto restoration and small-window controls at both text sizes.
Receipts and screenshots are under ignored `artifacts/native-project/`.
The browser bridge name is a test adapter; the processing child is Rust.

The original Python/Qt-model qualification is retained in
`desktop/tests/test_combination.py` and the history of this document. It is an
independent reference workflow, not a shipping runtime or silent fallback.
The broader native/reference limits remain in the native qualification ledgers.

## Consolidated integration check — 2026-11-08

The integrated checkpoint passes **90 native Rust tests** (one opt-in benchmark
ignored), **75 frontend tests**, the TypeScript/Vite build, and headless
Chromium/WebKit with Python and PATH unavailable in the processing child.
Both combined-pattern save and ordinary Save displayed pattern produce the
same scientific output. Detector contrast and Auto restoration are checked by
switching native configuration identities after project save/open.

This check found and corrected two consolidation regressions: the detector
intensity mount used the configuration list index instead of its stable identity,
and ordinary Save displayed pattern still selected the individual detector curve.
Receipts for the isolated integration checkpoint are copied to
`artifacts/detector-combination-integration/` in the consolidated checkout.
Concurrent, uncommitted correction/uncertainty work was preserved and was not
included in this checkpoint's test results. No preview was closed or restarted.

## Configuration toolbar and grouped browsing — 2026-11-08

`backend/tests/configuration_navigation.rs` covers grouped files, filename
position, numbered folders, MEC, custom folder/filename steps, active-only scope,
retained detector state, combined-result updates, project persistence, missing
matches, invalid rules, and atomic rollback on bad data or changed dimensions.
The browser check exercises settings, the MEC preset, custom rules, persistence
and reset through the real Rust child, and checks the compact toolbar/settings
at both text sizes. Combination controls are exercised from Calibration and Mask
as well as Integration. Processing remains Python-free in these checks.

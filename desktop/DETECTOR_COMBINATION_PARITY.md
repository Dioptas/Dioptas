# Detector combination in the consolidated Rust desktop

The detector-combination interface is included in `codex/rust-desktop`.
The original interface commit `6db5c58d` was merged by `37b7dfdf`; the
scientific commands were ported to `desktop/backend/src/combination.rs`.
The default application uses the Rust processor and compiled Dioptrin crate.
It does not use a Python wheel or fall back to Python or pyFAI for combination.

## Interface

Enable **Settings → Configurations → Enable configurations**. This existing preference remains off by default and persists across
restarts. The shared configuration bar supports add, duplicate, rename,
select and remove. Disabling configurations hides the toolbar and turns off
combination, retaining configurations and selection. A combined project enables
the toolbar when opened.

With two or more configurations, the top-bar configuration controls include the
selected detector's **Factor**, independent **Combine patterns** and **Combined cake** switches,
and **Save combined pattern**. These controls remain available across modes.
**Combined cake** merges calibrated 2D cakes in common diffraction coordinates.
Factor commits on blur or Enter and scales that
detector's scientific pixels before integration. Images remain independent;
combination produces calibrated patterns/cakes, never a detector-image mosaic.
Each configuration retains its image, calibration, masks, corrections and
scientific coordinates. Detector contrast, palette, linear/log and Auto settings
follow the stable configuration identity. Individual and combined cakes have
separate display settings. Pending scientific drafts prevent configuration changes.

The same bar provides previous/next **File** and **Folder** actions for all
configurations. Configure them under **Settings → Configurations → Browse
configurations**. Each detector advances from its own source, retaining
calibration, masks, corrections and factors. Combined products are recomputed.
The Image panel's individual browsing controls remain independent.

File and folder rules independently select a numbered part, counting from the
right, and a positive step size. Number 1 means the last number, 2 the preceding
number, and 0 tries numeric groups from right to left. Folder numbering counts
across the directory path. File browsing respects each configuration's name/time
ordering; time ordering uses the configured step instead of filename numbering.
Folder browsing normally retains the filename. Enable **Advance filename with
folder** to additionally advance a selected filename number using its own step. **Use MEC preset** selects all configurations,
automatic folder numbering, and the third filename number with unit steps,
matching the Qt convention. Every rule remains editable after applying the
preset. **Reset browsing** restores default number/step rules.
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

The final checkpoint includes the consolidated correction/variance work and
passes **104 native Rust tests** (one opt-in benchmark ignored), **75 frontend
tests**, Clippy with warnings denied, the TypeScript/Vite build, and the headless
Chromium/WebKit combination workflow. Settings persistence/reset, the MEC preset,
custom payloads and small-window layouts are checked in both browsers.

## Cake inspection and dedicated configuration settings — 2026-11-08

The control is labeled **Combined cake**. Native `validation_position` accepts
the cake's explicit `unit` and converts its radial coordinate into physical 2θ
before calculating linked contours and readouts. Omitting `unit` retains physical
2θ for existing Map/frame restoration calls. Invalid units/coordinates preserve
the previous inspection. Individual cakes remain in 2θ; combined cakes use Q
when the pattern uses Q and 2θ for 2θ/d patterns.

Configuration visibility and browsing preferences now have their own
**Settings → Configurations** tab. General no longer contains Processing or
Pattern navigation; plot navigation controls remain in the plot corners.

Verification passes **106 native Rust tests** (one opt-in benchmark ignored),
**75 frontend tests**, Clippy with warnings denied, and the TypeScript/Vite build.
Headless Chromium and WebKit exercise actual clicks on individual and combined
cakes in all three pattern modes, physical conversion, linked guides, the new
Configurations tab, and the absence of the removed Settings sections.

## Live Rust worker replacement — 2026-11-08

The native live preview rebuilds `backend/src`, Cargo, build script and data/resource
changes after a short debounce. The host remains open and retains UI state. It
starts a candidate Rust/Dioptrin process, waits for ordinary commands to finish,
saves a private owned-data checkpoint and restores it in the candidate. Only a
successful restore replaces the active stdio worker; compilation, startup and
restore errors leave the prior worker/session in place. Progress and cancellation
bypass the swap gate while an active calculation finishes.

The private checkpoint preserves all configurations, active selection and stable
identities; images and correction data survive even when input files disappear.
Settings, calibration picks/drafts, file polling state, linked inspection and the
current project path are restored. The original project is not overwritten and
the handoff metadata is excluded from future project saves. New native plans and
results are computed without triggering automatic output saves. Undo/Redo stacks
are retained by the version-2 worker checkpoint. Host source edits still restart the whole host;
this feature is for scientific worker updates in development, not bundled releases.

Headless tests compile a small Rust launcher around the real numerical worker,
change its source, verify automatic replacement and retained data, introduce a
Rust syntax error and verify the prior PID/state survive, then fix the source and
verify automatic recovery. Additional tests cover cancellation while a restart
is queued, bad executables, untitled sessions, owned images without source files,
project-file integrity, and generation of fresh configuration identities.

## Configuration enable switch and browsing layout — 2026-11-08

**Enable configurations** is the first control in its Settings tab. Turning it
off disables combined patterns and cakes, hides the toolbar and retains all
setups. A project opened with active combination enables the toolbar. Browsing
in that toolbar always applies to every configuration; individual Image-panel
arrows remain local to the selected detector. The settings scope selector and
redundant Multi-detector setups heading were removed.

File and folder rules have separate aligned sections with selected-number
previews. Linked filename changes are enabled with **Advance filename with
folder**; the MEC preset selects the third filename number. Turning configurations
off disables browsing preferences. Chromium/WebKit cover disabling combination,
retained setups, all-configuration payloads, reset, persistence and small windows.

## Undo/Redo across worker replacement — 2026-11-08

Version-2 development checkpoints retain mask Undo/Redo, calibration Undo/Redo and
integration edit history in every configuration, including mixed chronological
ordering, shared phase/overlay edits and redo branches. Current state and history
share a binary object graph so correction planes, curves and detector maps retain
shared ownership. Nonfinite numeric samples and exact floating-point bits survive;
calculation/EOS caches are rebuilt instead of being copied from old kernels.

The history sidecar is private to the worker handoff. Matching generations prevent
mixed checkpoint/history files from being applied, and ordinary `.dio` saves do
not include historical image/correction data. New workers can read version-1
checkpoints, but those older writers cannot export history; that one-time upgrade
starts with empty stacks. Future version-2 reloads preserve the full stacks.

Tests exercise Undo/Redo before and after repeated reloads in separate
configurations, calibration/integration ordering, branching after Undo, removed
correction sources, global phase/overlay changes, shared-array identity, all
floating-point bit patterns, and corruption cleanup.

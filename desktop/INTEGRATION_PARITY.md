# Integration workflow comparison

Implemented on `codex/desktop-integration` from checkpoint `4ef2ca3d`, using
current read-only Qt source at `/Users/clemens/Programming/Dioptas` and the
corresponding scientific models in this checkout. Comparison date: 2026-11-01.

The reference includes `widgets/integration/control/{ImageWidget,PatternWidget,
OptionsWidget,BackgroundWidget,CorrectionsWidget,OverlayWidget,PhaseWidget}.py`,
`widgets/integration/display/`, and `controller/integration/` (including the
nested overlay/phase controllers). The Qt view places its image/cake on the
left and control groups above the pattern on the right. The desktop now uses
that arrangement: the image/cake occupies the full-height left half, with the
controls in the upper-right pane and integrated pattern below them. Image/Cake
buttons switch the left display, retaining independent histograms. Both Qt-style
dividers support dragging, arrow keys and Home/double-click reset. The control
groups use the width of the upper-right pane rather than a tall sidebar. Left
mode navigation remains unchanged. This is a working, scoped workflow, not full
Qt replacement.

The former Options tab now lives in Settings → Integration: radial units,
automatic/manual binning, supersampling, 1D/cake azimuth ranges, cake bins,
solid angle, polarization, Poisson errors and zero trimming. The command and
project storage are unchanged; task controls stay in the Integration workspace.

| Qt workflow | Desktop implementation |
| --- | --- |
| Load image, previous/next, file step, number/time order | Existing ImgModel/FileNameIterator; file step and order controls; multiframe index shown when available; File Info exposes actual metadata |
| Load calibration | Native PONI chooser, existing CalibrationModel, shared calibration workflow retained |
| Image / cake switching and pattern inspection | Shared RasterView, PatternView and plot navigation; Qt Image/Cake switching, full-height image pane and controls-over-pattern split; linked clicks in all three views |
| Image intensity controls | Independent ImageIntensity for detector and cake, both default above the images; full-resolution arrays, original orientation, top-origin display rows, square detector pixels and existing gestures |
| Radial units and automatic/manual binning | Existing Configuration integration for 2θ, Q, d; Auto passes None to model; actual count displayed; manual counts 1–100000 |
| Supersampling | Existing CalibrationModel.set_supersampling, with fresh cake geometry to invalidate old pyFAI array caches; original image is still displayed at source resolution |
| 1D / cake azimuth options | Independent full/custom ranges, including sectors crossing ±180°; cake azimuth bin count; cake radial axis stays 2θ as in the synchronous Qt configuration model |
| Integration corrections | Solid angle, polarization and Poisson errors; XYE/FXYE require calculated errors; trim trailing zeros |
| Shared mask | Apply, transparency, native load/save; existing brush/eraser and stroke undo preserved; full dedicated Mask workspace belongs to the separate branch |
| Image background | Native load/remove and scale/offset, using ImgModel's subtraction pipeline; wrong-shape files are rejected before replacing the active background |
| Pattern background | Existing SmoothBruckner/PatternModel, smoothing, iterations, polynomial order and optional radial range; displayed data uses PatternModel.data; background range converts with radial unit changes; save fitted background |
| Corrections | Mean-normalized flat field with load/remove/use; cBN seat and oblique detector absorption with existing model parameters; active corrections rebuild on geometry changes |
| Pattern load / previous / next / save | Existing PatternModel iterators and Configuration writers; XY, XYE, CHI, DAT, FXYE; raw or background-subtracted save; background-only XY/CHI/DAT; no top-level Export pattern button |
| Autocreate | Existing Configuration._auto_save_patterns on explicit successful image load/navigation; output-folder chooser, selected formats and explicit Apply; normal and bkg_subtracted folders follow Qt; off after project reopen |
| Folder integration | Existing configuration.batch_model discovers same-extension files and their frames, integrates with current geometry/mask/corrections, reports progress and permits cancellation between frames; complete batch saves to model HDF5 or CSV; no duplicated Map workspace |
| Overlays | Native file import/current-pattern capture, visibility/color/scale/offset, delete, waterfall/reset, assign/remove pattern background; measured curves render on shared axes and participate in auto scaling |
| Phases | JCPDS/CIF/EOSMAT import, real PhaseModel pressure/temperature, apply-to-all, literature-reference selection when available, visibility/color/delete; computed reference sticks render in actual pattern units |
| Project persistence | Standard .dio models retain settings, backgrounds, corrections, overlays and phases. Autocreate is a session opt-in, never silently restored from a project. |

## Deliberate boundary handling

- Scientific ownership remains on DesktopBridge's single processing worker.
  Progress and the existing cancel event bypass it. A single pyFAI call is not
  interruptible; folder cancellation is observed between completed frames.
  Cancelled/failed batches restore the preceding complete batch, and the
  previously viewed file/frame is restored. Partial batches are not published.
- All new file/folder commands have Tauri native chooser routes, including
  cancellation. Updates, frame stepping, correction toggles and reference edits
  do not open dialogs. The browser chooser is only a test harness.
- Wrapped sectors explicitly select pyFAI's zero discontinuity while the
  calculation runs, then restore its normal ±π convention. Otherwise current
  pyFAI warns that a sector such as [150, -150] gives partial results. The
  numerical reference test uses the same explicit discontinuity with the Qt
  Configuration model. Cached angular-width arrays are cleared when switching
  discontinuities; the ordinary and wrapped cake comparisons pass at 1e-6 relative
  tolerance.
- Qt passes degrees to cBN but radians to oblique detector absorption. Its
  project correction reconstruction currently passes degrees to both. The
  desktop adapter normalizes these inputs, including after project load, so
  applied OIADAC corrections round-trip consistently. Original Qt/model files
  are unchanged.
- Overlay files keep their numerical x coordinates, matching Qt. They are not
  silently converted or assigned an inferred wavelength/unit. The UI asks for
  matching coordinates. Phase positions use PhaseModel conversion instead.
- Phase sticks show relative source reflection intensities (normalized to 30%
  of plot height); they are reference marks, not predicted measured counts.
- Numerical controls use explicit Apply actions. These do not launch model
  signal-driven background processing, a scientific HTTP service or Qt app.

## Integration contracts for merging the view branches

- `dioptas/desktop/integration.py` owns the IntegrationWorkflow mixin and all
  `integration_*` commands. Session only inherits/routes it, adds
  `state.integration`, refreshes PatternModel display data, invokes the scoped
  1D/2D adapters, and triggers autocreate after image loads.
- `desktop/src/integration.ts` owns IntegrationState and its command callback.
  `IntegrationView.tsx` contains the controls and display-choice toolbar;
  `integration.css` scopes its layout. `IntegrationWorkspace.tsx` owns the two
  resizable Qt-style dividers. App continues composing the existing
  detector/cake/pattern renderers. No renderer or gestures were copied. Identical
  cake payloads from overlay/phase-only changes preserve manual intensity limits.
- `State.bins` now accepts `null` for Qt automatic binning. `State.integration`
  is additive. Pattern responses optionally carry measured `curves` and
  `phaseLines`. PatternView's additive `curves`/`referenceLines` props default
  to empty and preserve calibration behavior; all modes share axes/gestures.
- `_next_image` accepts optional step=1. Linked detector inspection and ring
  contours use original-pixel geometry when supersampling is active. Default
  calibration behavior stays unchanged. PONI save temporarily restores physical
  detector pixel pitches so computational supersampling is never exported as
  changed detector hardware. Shared mask commands/contracts stay
  unchanged for the Mask branch to extend.
- Folder operations use the selected configuration's existing BatchModel, so
  the Map branch can consume the same results; no Map controls are added.
  A separate stdio progress/cancel protocol is unnecessary.

## Remaining Qt scope

- No new-file watcher / continuous beamline acquisition, image sum/average/save
  batch modes, stage/EPICS controls, or image ROI editing. Explicit loads and
  folder integration work; automatic unattended acquisition is not claimed.
- No transfer-function correction editor or formula/density-driven sample
  slab/cylinder/sphere/plate editor. Existing project data for these remain
  owned by the original models; this UI edits flat field, cBN and OIADAC only.
- No spottiness display/export, background inspection overlay, cake integral,
  azimuth-shift slider, image/cake export or detachable plot windows.
- Phase database browsing, material/reflection/EOS editing and phase-list
  save/load are not implemented. File loading and existing reference choices
  work. CIF conversion currently uses model defaults for cutoff/minimum d.
- No overlay drag/reorder or intensity matching; scale/offset and waterfall work.
- No configuration switching, explicit HDF5 source/dataset chooser, portable
  Python bundle or Windows/Linux qualification. Background unit conversion and
  overlay input units follow the qualifications above.

## Validation

- Own CPython 3.13.7 environment: `uv sync --python 3.13 --extra test`;
  own desktop dependencies: `npm ci`.
- `desktop/tests/test_integration_workflow.py`: 20 passed. Independent
  Configuration comparisons cover 2θ/Q/d, radial/cake binning, sectors, solid
  angle/polarization/errors; tests also cover automatic bins/supersampling,
  original-pixel linked inspection/PONI after supersampling, image subtraction/flat
  field, invalid-file/detector-shape preservation, absorption/project
  round trips, pattern background/range conversion, all five pattern formats,
  overlays/phases, autocreate, model HDF5/CSV and real-worker cancellation.
- Full desktop plus Pipeline/MainController/CalibrationController suite:
  144 passed, 5 skipped (optional Dioptrin and existing skip).
- `npm run build` and expanded real-model `npm run smoke` pass. Browser checks
  exercise calibration, histograms, gestures, compact/large-text layout, then
  Integration options, visibility choices, overlays, phases, backgrounds, saving,
  file order, mask and detector correction; no browser errors.
- `cargo test`: 3 passed, including new chooser-routing assertions.
- `npm run tauri:smoke`: bundled native WKWebView passes measured-image
  calibration and Integration settings (600 radial / 90 azimuth bins), overlay
  rendering, phase reflections and pattern save through stdio. Both histograms
  remain visible. No Qt application or scientific TCP listener; its own
  processing child is reaped. No primary-preview port is used. The final native
  rerun passed after macOS was unlocked, including the completed geometry/cache
  guards and original-pixel PONI save handling.

Evidence lives under ignored `desktop/artifacts/`, including
`integration-pytest.log`, `integration-regressions.log`, `browser-smoke.json`,
`integration-controls.png` and `tauri-native-smoke.json`. These are scoped
workflow checks, not detector-wide scientific accuracy qualification.

## Qt layout revision (2026-11-01)

The image spans the left column; controls and pattern share the right column,
with controls above the pattern. The initial image/analysis split is 50/50, with
38% of the right column assigned to controls. Splitters preserve usable minimum
pane sizes. Image/Cake selection does not integrate or recreate scientific
models. Both shared image instances retain their display preferences.

`integration_layout.mjs` checks pane alignment and proportions, pointer/keyboard
resizing, Image/Cake switching, 1000 × 760 layout and larger text. The expanded
browser suite also exercises calibration, all three plot gestures and the
scientific Integration controls in this arrangement. Native smoke checks the
same pane geometry before exercising the existing real-model workflow. Build,
expanded browser smoke and bundled WKWebView smoke pass for this revision.
Screenshots are `artifacts/integration-qt-layout.png`, `integration-qt-cake.png`
and `integration-qt-compact-large.png`; native evidence includes
`qtIntegrationLayout: true` and processing-child cleanup. Scientific model code
is unchanged by the layout revision.

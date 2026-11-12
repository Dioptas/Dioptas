# Integration Phase controls

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](REFERENCE_DATA.md) for retained fixtures and current checks.

The opt-in Rust implementation has a separate [native qualification ledger](NATIVE_INTEGRATION_PARITY.md), including the integration, phase and Batch/Map migration. The Python/Qt behavior and historical checks below remain reference evidence.

Compared on 2026-11-02 against the actual Qt PhaseWidget, PhaseController,
PhaseEditorWidget, PhaseEditorController, EosDatabaseController,
PhaseInPatternController, and PhaseInCakeController. The six principal widget/
controller files also match the original /Users/clemens/Programming/Dioptas
checkout byte-for-byte.

The Phase tab follows Qt's action rail, central phase table and right-hand
P/T step controls with list-file actions. The image remains left, controls
upper-right, and measured pattern lower-right. Scientific models, reflection
intensities, units, image pixels, histograms and mouse gestures are retained.

## Implemented

- Native multi-file JCPDS/CIF/EOSMAT selection. CIF import asks for Intensity
  Cutoff (%) and Minimum d-spacing (Å), initialized from the real experiment.
  Structure-backed reflection coverage extends to the complete measured pattern
  plus its Q margin, retaining any wider requested range. Wavelength and
  intensity cutoff remain those supplied at import.
- Row selection, keyboard Up/Down/Home/End, Enter/double-click to edit,
  Delete/Backspace to remove, and selected/all removal through the action rail.
  Selected rows scroll below pinned headings; both table axes scroll at small
  sizes rather than shrinking text and numeric inputs.
- Visibility, color, Name, P (GPa), T (K), Ref columns. The visibility heading
  follows Qt's any-visible rule. Existing DAC thermal-pressure state uses P₀.
- P step defaults to 1 GPa; T Step to 100 K. Step controls use Qt's 1–2–5
  stepping; row spinboxes use those increments. Typed values commit on Enter/
  blur. Steps survive tab and mode changes in the current application session.
  Apply to all delegates directly to PhaseModel. Temperature disables when
  the phase lacks thermal expansion; rejected conditions restore real state.
- Reference selectors expose full literature references, EoS and reproduction
  assessments, including Qt's warning states. Legacy/single-reference choices
  disable appropriately.
- Real EoS Material Database search through eos.search_materials, Recent/
  Favourites/All, diffraction filtering, record selection, source errors/fixed
  flags, pressure ranges, thermal indicators and full source qualifications.
  Loading uses build_jcpds with experimental coverage and bundled ownership.
  EoS-only and source-only/unvalidated records cannot become diffraction phases.
  Export uses the real EOSMAT writer. Recent/favourite choices live in the
  frontend and do not modify Qt settings.
- Phase Editor: lattice/symmetry, calculated lattice/volume values, active
  EoS/reference information, actual user-owned/legacy EoS parameters, editable
  h/k/l/intensity reflections, add/delete/clear, computed d₀/d/2θ, source reload,
  EOSMAT/JCPDS Save As and TXT reflection export. Only symmetry-independent
  lattice fields are editable. Published records and bundled structures retain
  PhaseModel's read-only ownership protections.
- Save/Load List use Qt's six CSV columns: file, visibility, color, name,
  pressure, temperature. Loading appends, preserves False visibility, resolves
  relative files against the list and restores state on failure. CSV quoting
  supports commas in filenames/names.
- Qt-style colored phase legend with P/T labels. Existing visible-range phase
  stick normalization and relative-intensity detector/cake strokes are unchanged.

At compact heights the P/T column can scroll while Save List/Load List remain
visible. Control text stays 14 px / 16 px at standard/larger text settings.

## Remaining differences

- The editor is an in-app modal rather than Qt's separate nonmodal window.
  Atomic-site/space-group editing, lattice ratios, EoS/thermal-type changes,
  advanced thermal parameter forms and record add/duplicate/edit/delete/default
  management remain outside this scoped editor.
- The database lacks Qt's explicit assumed tetragonal perovskite option and
  external reconstruction-report/catalog buttons. No assumed structure is
  silently supplied. It initially opens All rather than an empty Recent view;
  diffraction availability is generic rather than structure/peak classifications.
- Name/Ref columns scroll with fixed minimum widths, without Qt's header resizing.
- Qt's legacy list format references source files; it embeds neither phase
  contents nor active literature-reference choices. Save List disables with an
  explanation for database-only/unsaved sources, preventing unloadable files.
  Save project retains phases, edits and references in a self-contained .dio.
- Evidence covers Chromium, WebKit and macOS WKWebView, not Windows/Linux or
  interactive native chooser automation. Native routing and explicit file paths
  are checked separately.

## Verification

Own CPython 3.13.7 environment and desktop/node_modules in the assigned
codex/phase-qt-controls worktree. No port 1420 use or primary-checkout changes.

- npm run build passes TypeScript and production compilation.
- npm test: 20 passed, including existing phase-line intensity scaling tests.
- Full desktop Python suite: 162 passed, 5 skipped before the final two added
  validation tests. Final focused Phase suite: 9 passed, covering real model
  conditions, lists/rollback, published ownership, EoS-only rejection, CIF
  wavelength/cutoff, editing/export/reload and failed multi-file restoration.
- scripts/phase_controls.mjs with Chromium and --webkit: real Python bridge
  imports, conditions, stepping, visibility, lists, editor, database, legend,
  long-table selection and 1000 × 668 layouts at both text sizes.
- npm run smoke: full real-image calibration/Integration/Mask browser regression
  passes, including phase guide canvas strokes, histograms and plot navigation.
- Cargo tests: 8 passed, including chooser routing and real stdio child lifetime.
- npm run tauri:smoke: bundled WKWebView passes calibration, Integration, Mask,
  Phase table, multiplicative steps, tab persistence, pressure/lattice edits,
  list append and database opening. The processing child exits; no Qt
  application or scientific TCP listener is created.

Ignored screenshots/reports: desktop/artifacts/phase-controls.png,
phase-compact-{normal,large}.png, phase-database.png,
phase-controls-{chromium,webkit}.json, tauri-native-smoke.json.

## Files specific to this change

- New UI: src/IntegrationPhaseControls.tsx, integrationPhaseControls.css,
  IntegrationPhaseLegend.tsx, integrationPhaseLegend.css, integrationPhase.ts.
- New scientific adapter: dioptas/desktop/phases.py; IntegrationWorkflow routes
  commands and phase snapshots into it. No Qt model/controller files changed.
- Narrow shared UI changes: src/IntegrationView.tsx mounts the Phase component;
  src/PatternView.tsx imports/renders the isolated legend; src/integration.ts
  and types.ts declare additive Phase state/response types. App.tsx is untouched
  by this task.
- File routing: src-tauri/src/main.rs, dioptas/desktop/__main__.py and the
  browser test host scripts/bridge_host.py.
- Verification: tests/test_phase_controls.py, scripts/phase_controls.mjs,
  scripts/phase_native_smoke.js, and narrow native smoke injection/report hooks
  in scripts/tauri_smoke.js and src-tauri/src/main.rs.
- Documentation: this file and the Phase entries in INTEGRATION_PARITY.md.

The checkout already contained snapshotted changes from other chats. Those
baseline modifications were preserved when isolating the Phase commit. Phase
was then integrated into codex/react-desktop alongside its newer Image, Pattern,
Overlay and readout workflows. Table presentation is now shared with the other
views through DataTable, TableScroll and TableActions; see desktop/README.md.

## Integration verification (2026-11-03)

The primary checkout passes the combined desktop Python suite (189 passed,
5 skipped), the 35 JavaScript numerical/transfer checks, and the Phase/Overlay
browser workflows. The Phase browser check also compares actual header, field
and color-swatch styling across Phase, Overlay and calibration at both text
sizes. The original source reflection-intensity behavior remains unchanged.

The combined full browser regression, Map browser workflow, Chromium/WebKit
Phase and Overlay workflows, and bundled Tauri smoke also pass after sharing
the table primitives. Native checks retain the pressure/lattice/list/database
operations, full-resolution pixels, independent histograms, and stdio child
cleanup. All work remains local; no push was requested.

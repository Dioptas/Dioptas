# EoS Material Database explorer

Implemented and checked on 2026-11-03 in `codex/phase-database-explorer`,
starting at `d4efd68a`. Scope is the database explorer, not the Phase Editor.

The Qt reference is `dioptas/widgets/EosDatabaseDialog.py`,
`dioptas/controller/integration/phase/EosDatabaseController.py`, and the
record/provenance fields in `dioptas/widgets/EosRecordDialog.py`. These files
match the read-only current Qt checkout in `/Users/clemens/Programming/Dioptas`.
The new interface continues to use the existing Python models over Tauri stdio.

| Qt behavior | React explorer |
| --- | --- |
| Ranked name/formula/alias and chemical-composition search | Same `eos.search_materials` function; debounce, pending state, stale-result rejection and explicit retry |
| Recent, Favourites, All; global search with view restoration | Available; recent materials retain most-recent-first order and a 20-material limit |
| Diffraction filter and material status | Distinguishes crystal structure, reference peaks, assumption required and EoS only; the filter hides the last two |
| EoS table, thermal indicator, authors/year, fit pressure range | Available, including separate source record labels and fixed/error qualifiers |
| Sort by scientific columns | Available; numeric sorting uses source numbers; the selected record keeps its original model index |
| Interactive record-column widths | Drag borders, use left/right keys on a border, or double-click to fit contents |
| Held defaults and source-only records | Held materials remain unselected until an explicit choice; model loading restrictions remain enforced |
| Load selected record or double-click | Available; table arrows/Home/End select, Space selects, Enter loads the focused record when permitted |
| Export material, reconstruction report and Peritheos documentation | Material export retains all records; documentation actions resolve URLs from the selected bundled record in Python and open the system browser |
| Assumed CaSiO3 structure | Same existing model opt-in for the two supported tetragonal entries, with the complete approximation note; loading/export use an annotated copy |
| Escape and initial search focus | Available, with focus restored after closing; Cmd/Ctrl+F focuses search |

The record inspector groups assessment/source text, all EoS and thermal
parameters, and the complete bundled model record in separate tabs. The JSON
is the existing model's normalized record, not a new transcription of the
publication. Null errors stay unknown; fixed values and independently reported
errors remain distinct. The fit pressure interval is labelled as the interval
constraining the published EoS, not a phase-stability claim. Model-specific
configuration, volume basis, source lineage and audit qualifications remain
available in the full record rather than being flattened into guessed fields.
No values, published records or source scientific models were changed.

The resizable dialog keeps actions in its footer, independently scrollable
materials/records/inspection panes, sticky table headers and a readable
horizontal record-table scrollbar. Short search results release space to the
records and inspector. Long row labels show two lines; the selected record's
full label and qualifications remain visible in the inspector. Compact windows
can scroll the dialog body while keeping footer actions visible.

Implementation is separated into `PhaseDatabase.tsx`,
`DatabaseRecordInspector.tsx`, `DatabaseColumnResize.tsx`, `phaseDatabase.css`,
`phaseDatabaseTypes.ts` and `dioptas/desktop/phase_database.py`. Shared changes
are limited to extracting the old dialog and its styles, forwarding the catalog
contract, the documentation route, explicit assumed-structure arguments and
loading a scoped native smoke helper.

## Verification

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest desktop/tests -q`:
  **194 passed, 5 skipped**.
- Focused database/phase/Qt controller run: **56 passed**. The database contract
  is compared with Qt for all **233 materials / 678 records**, including source
  fields, error/fixed distinctions, assessments and documentation URLs.
- `desktop/tests/test_phase_database.py` also checks ranked formula search,
  held/source-only entries, assumed-structure load/export round trips, unchanged
  bundled documents, and selected-record browser URL resolution.
- `npm test`: **37 passed**. `npm run build` passes.
- `node desktop/scripts/phase_database.mjs` and the `--webkit` variant pass:
  real-model ranked searches, delayed stale responses, incomplete-response retry,
  malformed stored preferences, favourites/view restoration, empty states,
  held defaults, sorted identity and Enter loading, parameters/full metadata,
  recent ordering, EoS-only export, explicit assumptions, focus/keyboard behavior,
  column drag/key resizing and 1440×1000, 1000×668, 800×600 layouts at both text sizes.
- Existing `phase_controls.mjs` checks pass in Chromium and WebKit.
- Prettier checks pass for the new frontend/scripts. `cargo fmt --check` still
  reports pre-existing formatting in `color_picker.rs` and unrelated portions
  of `main.rs`; the added native-smoke include follows rustfmt formatting.
- `npm run tauri:smoke` passes with embedded assets. A scoped native check covers
  initial search focus, held defaults, no-hit clearing, sorting, column resizing,
  original-record inspection and loading the exact selected real model record.
  Existing calibration, mask, integration, binary transfer and child-process
  cleanup checks also pass; the host reports no Qt application or scientific TCP
  listener.

## Remaining differences and limits

- React opens All with the diffraction filter enabled, preserving the preview's
  useful initial catalog view. Qt initially opens Recent with the filter off.
- Recent/favourite IDs use preview-local storage, separate from Qt's INI settings.
  This work does not migrate user settings between hosts/origins.
- Dialog/column sizes reset on reopening; the Qt vertical table splitter is not
  reproduced. The dialog and record columns are resizable within a session.
- The parameter inspector uses source parameter names. General model-specific
  units/configuration are retained in the full record rather than guessed for
  unfamiliar coefficients. The main table retains Qt's GPa and Å³ columns.
- Documentation URLs and UI routing are tested; external browser launch is
  mocked in automated tests. Website availability/content and Windows/Linux
  native behavior are not established by these checks.
- Bundled records remain read-only here. Record creation/editing belongs to the
  separate Phase Editor workflow. No new scientific validation or refit is claimed.

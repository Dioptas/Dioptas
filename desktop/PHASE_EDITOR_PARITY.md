# React/Tauri phase editor

Implemented on `codex/phase-editor-ergonomics`, starting from `d4efd68a`.
Compared against Qt's `PhaseEditorWidget`, `PhaseEditorController`, `EosRecordDialog`,
`SpaceGroupSelector`, and the shared `PhaseModel`. The widget in the current
`/Users/clemens/Programming/Dioptas` checkout matches the reference in this worktree.

## Scientific behavior and Qt coverage

| Area | React implementation |
| --- | --- |
| Reference lattice | All eight Qt symmetries, independent a₀/b₀/c₀ and angle fields; constrained fields remain disabled. Trigonal and rhombohedral settings remain distinct. |
| Ratios and increments | Qt's a/b, c/a and c/b operations, with symmetry-specific availability; editable length, angle and ratio increments. |
| Calculated lattice | a, b, c, V₀ and V at session conditions, with explicit Å, degrees and Å³ units. DAC cold-pressure inputs are identified as P₀. |
| EoS | The installed adapter's 11 room-temperature types. Dynamic fields include reference pressure for BM2Reference, K₀″ where supported, and material normalization data for Holzapfel and molar thermal models. |
| Thermal models | None, the legacy constant-coefficient correction, and all 18 installed constructor models. Fields and required/optional defaults come from their actual signatures; configuration choices use the shared model definitions. Nullable defaults are omitted from EOSMAT rather than serialized as invalid null coefficients. |
| AlphaKT distinction | The constructor-based thermal-reference-state model retains its explicit model identifier in legacy v2 records and exports. It is not silently interpreted as the older JCPDS coefficient correction when reloaded or reselected. |
| Records | Selection, add from session values, duplicate as custom, rename, delete and set default. Published bundled records and bundled structures remain protected by PhaseModel. Custom copies keep source records intact and receive the existing model's unvalidated/custom status. Complete record metadata, including reported errors, fixed parameters and source evidence, is inspectable and retained. |
| Atomic positions | Element, fractional coordinates, occupancy and existing isotropic displacement fields; add/remove sites; editable space group by symbol/number, with the same 230 reference-group choices as Qt and retention of an explicit material setting. All edits use Qt's PhaseModel entry points and recalculate diffraction at the session wavelength. |
| Composition | Assumed/edited structure flags, original site metadata, stored Z, independently calculated Z and the composition diagnostic. Structural edits do not rewrite the formula, stored Z, electron count or EoS normalization. Coordinates stay in their existing basis and origin. |
| Reflections | Editable h/k/l/intensity; calculated d₀/d/2θ; stable-index view sorting, select all/multiple delete, copy selected/all rows, add, confirmed clear, and a dedicated TXT export chooser. The displayed table is rounded; copy retains the underlying numbers and TXT export retains 17 significant digits. |
| Save/reload | Valid edits apply immediately to the session; Save As writes a file and Reload restores its source. EOSMAT exports include a legacy phase's live EoS even without a named record. Legacy JCPDS export is allowed for BM3 peak tables, and rejected before writing when it would discard advanced EoS models, records/provenance or atomic structure. Use EOSMAT for those materials. |

New model selection uses Qt's existing starting-estimate helper. These are
explicitly described as starting estimates, not measured or fitted coefficients.
Inspecting a source does not replace its scientific values with defaults.

## Organization and interaction

The parameter column follows Qt's **Volume & structure / Equation of state**
pages, beside an independently scrolling reflection table. The resizable dialog
has a fixed action footer, sticky table headers, visible scroll surfaces,
explicit units, source/ownership state, and collapsible provenance and
normalization details. Both application text sizes are retained.

Numeric drafts accept scientific notation. Enter or blur commits a valid value;
Escape restores the applied value without closing the dialog. Invalid values
have an inline message and cannot be saved as a draft. Edits are serialized so
rapid Tab-driven entry survives model updates. Backend scientific rejection
restores the complete phase state and displays the reason inside the modal.
Arrow keys step lattice values; parameter tabs support arrow/Home/End navigation.
Adding a reflection focuses its h field; closing restores focus to the opener.

Feature code is isolated in `PhaseEditor*.tsx`, `phaseEditorTypes.ts`,
`phaseEditor.css`, and `dioptas/desktop/phase_editor.py`. The shared phase-controls
file only imports/calls the extracted editor. No App.tsx, types.ts, session.py,
database explorer or scientific-model changes are required.

## Verification

- Real-model editor tests compare lattice ratios, reflection positions, atomic
  edits and hot P/T results against direct PhaseModel calls used by Qt.
- Round trips cover custom/bundled ownership and source-record preservation,
  Debye parameters, constructor AlphaKT, structure edits and lossless EOSMAT
  saves; invalid edits restore values and JCPDS loss is rejected before writing.
- Browser interactions use the real Python bridge in Chromium and WebKit:
  draft validation, Escape, Tab/focus, rapid entry, sorting/copy, reflection
  actions/export, constructor/configuration controls, site/group edits, record
  actions, focus return, and both text sizes at 1000 × 668.
- Existing phase-controls browser regression, Qt editor/controller tests,
  integration/calibration/combined-view regressions, JS tests and build pass.
- Bundled Tauri/WKWebView smoke exercises numeric validation/Escape,
  lattice/reflection/thermal-constructor editing, existing calibration and
  integration workflows, full-resolution transfer and processing-child cleanup.
  No primary-preview server or user window is used.
  The native probe focuses inputs, uses cancelable keyboard events and waits
  for the editor queue; earlier timing-only probe attempts intermittently failed.

Run the focused checks from this checkout:

```sh
.venv/bin/python -m pytest -n 0 desktop/tests/test_phase_editor.py
cd desktop
npm run build
node scripts/phase_editor.mjs
node scripts/phase_editor.mjs --webkit
node scripts/phase_controls.mjs
npm run tauri:smoke
```

## Remaining differences

Qt's full EosRecordDialog can edit citation, range, reported uncertainty and
fixed-parameter metadata. React currently retains and exposes that metadata,
but edits record labels and supported live model parameters rather than the
complete provenance form. Unsupported published equation types remain
inspectable through their complete record metadata; the room-temperature
selector offers the adapter's existing editable types.

Elements are entered as validated symbols rather than chosen in Qt's periodic
table dialog. Native macOS and browser tests do not qualify Windows/Linux
packaging. Source-only scientific records retain the existing model's loading
and validation restrictions. This is scoped parity, not complete Qt replacement.

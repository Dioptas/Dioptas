# React/Tauri phase editor

The current Rust publication-metadata workflow is documented and qualified in
[Native EoS publication record editing](PHASE_RECORD_METADATA.md). It supersedes
the historical metadata/range limitations below.

The opt-in Rust implementation has a separate [native qualification ledger](NATIVE_INTEGRATION_PARITY.md), including the integration, phase and Batch/Map migration. The Python/Qt behavior and historical checks below remain reference evidence.

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
| Records | Selection is available for all materials. Adding, duplicating, renaming, deleting, clearing, choosing a default and editing EoS parameters require an editable material; bundled database materials first require Edit a copy. This is enforced by the UI and desktop processing boundary. Deletion reconciles pressure reductions and observation-view links while preserving shared observations. A record used as another record's parent cannot be deleted alone. Edits are validated and applied atomically. Clear all retains the structure, resets live EoS/thermal coefficients and allows a structure-only save or a new custom EoS. Custom copies keep source records intact and receive the existing model's unvalidated/custom status. Complete record metadata, including reported errors, fixed parameters and source evidence, is inspectable and retained. |
| Ranges | Experimental P/T envelopes and intended-validity P/T limits are shown separately, in GPa and K. Custom records can edit or clear each pair; bundled records display them read-only. Apply ranges validates ordered, finite pairs and saves them atomically without rewriting source records. Pending drafts disable material Save/Save As until applied or reset. Range edits survive EOSMAT save/reload and retain source notes with an explicit user-edit qualification. |
| Atomic positions | Validated element symbols and a periodic-table picker, fractional coordinates, Occ. and existing isotropic displacement fields; add/remove sites; editable space group by symbol/number with the number displayed, the same 230 reference-group choices as Qt and retention of an explicit material setting. All edits use Qt's PhaseModel entry points and recalculate diffraction at the session wavelength. Derived Wyckoff labels use the declared Hall setting and each site's orbit, including coincident sites. |
| Composition | Assumed/edited structure flags and original site metadata are retained. Structural edits do not rewrite the formula, stored Z, electron count or EoS normalization. Coordinates stay in their existing basis and origin. Composition diagnostics remain available in the model but are omitted from the editor. |
| Reflections | Compact signed h/k/l fields and intensity displayed to four significant digits (full precision on focus, in calculations and export); calculated reference/current d, 2θ and Q pairs with a position-column selector; stable-index view sorting, select all/multiple delete, copy selected/all rows, add, confirmed clear, and a dedicated TXT export chooser. The displayed table is rounded; copy retains the underlying numbers and TXT export retains 17 significant digits. |
| Save/reload | Valid edits apply immediately to the session. Material names are editable independently of filenames. Save As atomically writes EOSMAT and associates the editable phase with that file; Save writes subsequent changes to the same file, and Reload restores it. EOSMAT exports include a legacy phase's live EoS even without a named record. Legacy JCPDS export is allowed for BM3 peak tables, and rejected before writing when it would discard advanced EoS models, records/provenance or atomic structure. Use EOSMAT for those materials. |

New model selection uses Qt's existing starting-estimate helper. These are
explicitly described as starting estimates, not measured or fitted coefficients.
Inspecting a source does not replace its scientific values with defaults.

## Organization and interaction

On Tauri, Phase Editor is a separate, decorated and resizable native window.
Its native title bar supplies the window controls; the embedded title/close
header is rendered only in the browser fallback. Record deletion and clearing
use a small confirmation popup beside the invoking button, with Escape/Cancel
and focus return, rather than an extra row below the editor.
It shares the existing processing session, can be moved beside the main plots,
and does not block the main workspace. Edits refresh the phase table and plot
using phase-only replies, without rebuilding detector/cake/mask snapshots,
resending the detector image or resetting its zoom/contrast. Live refreshes do
not activate the main window's global busy state. Revision-aware synchronization
avoids reading the editor again for its own completed edit; genuine external
changes still refresh it. Stable
phase identities prevent a detached editor from changing a different phase
after list removal or project replacement. Closing an editor does not stop
processing; an in-flight edit finishes before its window closes. Browser and
legacy previews retain the modal fallback.

**Edit a copy** adds an independent, editable material to the session and selects
it for editing, without any export/import step. The original bundled phase is
retained. Scientific values and reflection coverage are copied without refitting;
source identity and validation metadata are recorded as provenance, and the
copy's EoS records are explicitly marked as user-owned/unvalidated. Copies can
be saved in a project or as EOSMAT. Edit a copy is beside Save and Save As in
the fixed footer. Record actions are always visible beside the record selector
in a compact icon toolbar, with tooltips and accessible names for duplicate,
add, set default, delete and clear all. Record/name/model controls come first,
followed by the EoS and thermal parameter tables. Normalization data, scientific
assessment and complete record metadata are disclosed at the bottom. Published
record names are visible but protected; custom names remain editable.
The assessment badge retains the model's wording: green for reproduced/parity,
amber for similar/limited checks, red for not reproduced/do not use, blue for
documented reconstructions/refits and neutral for unavailable/unassessed results.
Tooltips retain scope and qualifications. Custom copies remain unassessed and
do not inherit a source's green badge. Material and EoS names have distinct editable fields. Numeric EoS,
normalization and thermal parameters use shared, fixed label, value and unit
columns. A wide parameter pane fits two groups per row; a narrow pane uses a
compact single group. Pairing starts at 37.5 em of available pane width
(525 px at standard text size); the breakpoint follows text size. Long units and
configuration choices span the full row and align with the first group.
Labels align right beside their controls, including model/record selectors and
configuration choices. Unitless rows reserve the unit column. Constructor
defaults retain an inline asterisk and per-field tooltip; there is no separate
defaults disclosure.
The EoS parameter pane scrolls vertically only. Controls, unit cells and expanded
provenance wrap within the pane; horizontal scroll positions remain zero across
both text sizes and the tested 1000, 1200 and 1440 px windows.
Thermal coefficients use scientific symbols, explicit constructor units and
plain-language tooltips (including constant-volume derivatives). Model-specific
scaling is retained: for example, DO2007 coefficients displayed in 10⁻⁶ K⁻¹
remain distinct from the Dewaele2006 K⁻¹ coefficients. Display notation does not
change parameter keys, numerical values, calculations or exported records.
Projects written by the earlier deletion implementation reconcile stale dataset
record links before constructing their EoS on load. Export performs the same
repair for explicitly edited record sets; remaining cross-record dependencies
and other schema errors are still validated.

Wyckoff annotations use the pinned Moyo v0.15.0 reference table (MIT license;
attribution and generation inputs are in `dioptas/resources/data/wyckoff/`).
Classification does not infer a different symmetry or overwrite source labels.
Unknown settings or unmatched coordinates report an unavailable derived label.

The parameter column follows Qt's **Volume & structure / Equation of state**
pages, beside an independently scrolling reflection table. Both parameter panes
use explicit classic scrollbars: the track and thumb remain visible at rest
whenever content overflows, including on macOS WebKit. The resizable dialog
has a fixed action footer, sticky table headers, visible scroll surfaces,
explicit units, source/ownership state, and collapsible provenance and
normalization details. Both application text sizes are retained.

Numeric drafts accept scientific notation. Enter or blur commits a valid value;
Escape restores the applied value without closing the dialog. Invalid values
have an inline message and cannot be saved as a draft. Edits are serialized so
rapid Tab-driven entry survives model updates. Backend scientific rejection
restores the complete phase state and displays the reason inside the modal.
Visible up/down controls and arrow keys step each editable lattice/ratio field
by its configured Length, Angle or Ratio increment. Constrained fields keep
their controls disabled. Lattice rows share label, input and unit column widths;
dimensionless ratios reserve the same unit space. Parameter tabs support
arrow/Home/End navigation.
Wheel scrolling over editable numeric fields also steps their values and consumes
the event, so it does not scroll the containing pane. Native number inputs share
this behavior throughout the application; explicit steps and bounds are retained
(an unspecified increment is 1). Phase P/T fields use the configured increments,
and phase step selectors retain their multiplicative 1/2/5 sequence. Rapid phase
condition edits are queued without disabling the table. Consecutive pending
pressure or temperature values for the same phase are coalesced to the latest
requested value while an earlier edit is being applied. Discrete commands such
as Save, Delete, and linked-condition changes remain ordering barriers. Stable
phase identities also protect queued edits after list changes. Disabled/read-only native
fields are unchanged. The shared handler ignores horizontal scroll/pinch gestures.
Adding a reflection focuses its h field; closing restores focus to the opener.

Feature code is isolated in `PhaseEditor*.tsx`, `NativePhaseEditor.tsx`,
`phaseEditorWindow.ts`, `phaseEditorTypes.ts`, `phaseEditor.css`,
`src-tauri/src/phase_editor.rs`, and `dioptas/desktop/phase_editor.py`. The shared phase-controls
file imports/calls the extracted editor and routes native opens. Small shell
hooks mount the child window and synchronize session revisions; the backend adds
a readonly phase-workspace snapshot. Database explorer and scientific models
are unchanged.

## Verification

- Real-model editor tests compare lattice ratios, reflection positions, atomic
  edits and hot P/T results against direct PhaseModel calls used by Qt.
- Round trips cover custom/bundled ownership and source-record preservation,
  Debye parameters, constructor AlphaKT, structure edits and lossless EOSMAT
  saves, independent material names, file association and subsequent Save;
  invalid edits restore values and JCPDS loss is rejected before writing.
- Site-label checks cover all 3,467 representatives across all 530 Hall settings,
  coincident gold sites and rhombohedral/hexagonal setting distinctions.
- Record regression checks cover each Gold record's delete/save/reload path,
  shared pressure-reduction/observation links, dependency protection, rollback
  after a failed calculation, clear/save/reload followed by a new EoS, and
  recovery/export of a project affected by the earlier deletion implementation.
- Protection checks reject direct bundled-material add/duplicate/edit commands
  and retain the original records. Range checks cover independent experimental
  and validity limits, clearing, invalid-pair rollback, save/reload, pending-draft
  Save protection and unchanged source material.
- Browser overflow checks cover four thermal models, all details expanded,
  both text sizes and three widths, verifying control bounds and zero horizontal
  scroll rather than merely hiding overflowing controls.
- Browser interactions use the real Python bridge in Chromium and WebKit:
  draft validation, Escape, Tab/focus, rapid entry, sorting/copy, reflection
  actions/export, numeric wheel stepping (including bursts, bounds, intensity
  precision and pane-scroll suppression), constructor/configuration controls, periodic-table selection,
  site/group edits, material-name/save actions, always-visible record
  actions beside the selector, control/detail ordering, source badge colours,
  unassessed custom copies, aligned label/value/unit columns (including Holzapfel normalization),
  focus return, and both text sizes at
  1000 × 668. Gated 25-notch pressure bursts in both directions produce at most
  two calculations (in flight and latest pending), keep the table enabled and
  apply the final conditions to both linked phases.
- Existing phase-controls browser regression, Qt editor/controller tests,
  integration/calibration/combined-view regressions, JS tests and build pass.
- Bundled Tauri/WKWebView smoke exercises numeric validation/Escape,
  independent native title-bar movement, persistent parameter scrollbars,
  compact indices, lossless intensity display/editing, material naming and Save,
  lattice/reflection/thermal-constructor editing, adjacent record-confirmation
  placement, delete/save and clear/cancel, absence of a duplicate native close
  header, no main-window busy flicker during edits, no redundant editor refresh
  after a local edit, lattice and phase-table wheel
  stepping, existing calibration and
  integration workflows, full-resolution transfer and processing-child cleanup.
  No primary-preview server or user window is used.
  The native probe focuses inputs, uses cancelable keyboard events and waits
  for the editor queue; earlier timing-only probe attempts intermittently failed.
- The focused phase-controls check also covers existing overlay wheel stepping.
  The broader overlay script timed out at its earlier curve-selection stroke
  assertion, before reaching its wheel checks; no overlay component was changed.
- Command-queue unit checks cover coalescing, discrete-action ordering, independent
  phases/fields and recovery after a rejected request. Backend checks assert that
  live native edits and P/T updates do not construct a full workspace snapshot.

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
but edits record labels, experimental/validity P/T ranges and supported live model parameters rather than the
complete provenance form. Unsupported published equation types remain
inspectable through their complete record metadata; the room-temperature
selector offers the adapter's existing editable types.

Native macOS and browser tests do not qualify Windows/Linux
packaging. Source-only scientific records retain the existing model's loading
and validation restrictions. This is scoped parity, not complete Qt replacement.


## Contextual model documentation — November 11, 2026

The EoS and thermal-model selectors now show a short explanation and a link to
the corresponding section of the PeriTheos manual. Thermal choice fields show
the selected law beside the control: expansion, reference volume, bulk modulus,
Debye temperature and thermal-pressure reference. Debye help distinguishes the
integrated Grüneisen law from the variable-exponent convention, shows the q=0
limit, defines symbols, and states the different logarithmic volume derivative
of the variable-exponent law. Other law equations include the absolute- versus
reference-temperature expansion convention and the cubic reciprocal-modulus
polynomial. Help follows the backend's current accepted field values.

Equations use local MathML, with accessible equation labels, without loading a
remote renderer or performing scientific calculations in the UI. Descriptions
and links are maintained in `phaseModelHelp.ts`, checked against the PeriTheos
equation reference and the native implementation. Unknown future models fall
back to the relevant manual overview. Documentation remains available for
read-only records.

Native links use the host's `open_peritheos_manual` command to open the system
browser. This command accepts only the PeriTheos manual origin. Existing catalog
record links retain their current behavior through the same system-browser
launcher. Help navigation does not send a scientific edit or replace the editor
page. Browser previews use ordinary external links. `npm run test:phase-model-help`
checks schema choice coverage, MathML rendering in Chromium/WebKit, accepted
native law changes, equation/help updates and the native link invocation/error
path. Host tests cover the manual origin and invalid URL rejection.

Verification passes with the matching native processor: frontend production
build, 117 frontend checks, 33 host tests, the new model-help check, and the
existing publication-metadata regression in both Chromium and WebKit. All 27
linked equation-reference anchors were checked against the public manual.
The actual OS browser was not opened during headless verification.

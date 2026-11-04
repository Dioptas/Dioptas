# EoS Material Database explorer

Current interface, simplified on 2026-11-04 after feedback on information overload.
The browser is a material/record picker. Full scientific documentation is reached
through the selected record's Peritheos and reconstruction-report links.

## Visible workflow

- Search by material name, formula or alias, using the existing ranked model search.
- All, Recent and Favourites show only materials with crystal structures or reference
  peaks usable for phase lines. All is first. The redundant diffraction column and
  filter control are removed, as is the duplicate Clear button; the search field's
  native clear icon remains available. Favourites use an icon-only star.
- Select a material, then its record. The record table begins with author/year,
  followed by the EoS type, thermal-model availability, and the source fit pressure
  interval. The thermal indicator's tooltip gives the actual model name; the pressure
  heading explains that the interval is not a phase-stability range. Non-numeric
  source statuses (for example, reference model) are preserved. A variant column
  appears only for materials whose records contain otherwise ambiguous
  author/year/type combinations.
- Variant names retain catalog wording; repeated citation prefixes are removed.
  Full record labels remain available on hover. Rows stay one line high.
- Load the selected record or export the material with all its records.
- Open Peritheos or the reconstruction report for scientific detail.

The browser no longer shows assessment/source tabs, parameter tables, raw JSON,
volume/modulus columns, long assessment text, material notes or a permanent
explanatory legend. It uses two separated lists in a smaller resizable dialog,
with persistent footer actions and no horizontal record-table scrolling. The material
pane is a fixed 180 px high with stable column positions for any number of search
results; matching materials scroll inside it.

Held defaults still require an explicit record selection. Source-only records still
block loading and show one brief notice, with the complete model reason in its
tooltip. Materials without diffraction data, including entries needing an assumed
structure, are excluded from this picker. Their source records and explicit model
assumption support remain intact in the Python boundary.

Source data, units, qualifications, provenance, published-record protections,
record identity, defaults, assumptions, export and loading semantics remain owned
by the existing Python models. This change alters presentation only; it adds no
scientific validation or refits. The complete catalog payload remains intact.

## Qt reference and integration

The reference workflow is implemented by `dioptas/widgets/EosDatabaseDialog.py`
and `dioptas/controller/integration/phase/EosDatabaseController.py`; record metadata
are also represented in `dioptas/widgets/EosRecordDialog.py`. The simplified React
presentation deliberately omits Qt's detailed comparison columns.

The explorer is integrated into `codex/react-desktop` alongside the detached Phase
Editor. It retains ranked search, favourites, most-recent-first history (20 items),
record sorting, keyboard selection/loading, double-click loading, search focus,
Escape dismissal, and selection visibility after resize. Record-column resizing
and the built-in inspector were removed with their components.

## Verification

- `npm run build` and 40 JavaScript tests pass.
- `node desktop/scripts/phase_database.mjs` and `--webkit` exercise real records:
  stale/incomplete searches, favourites/history, empty states, concise reference-first
  columns, absence of the old inspector, distinct same-author variants, documentation
  routing, selection identity after sorting, held/source-only load restrictions,
  model loading/export, exclusion of EoS-only/assumption-only materials, the fixed
  material pane and column positions, native search clearing and the star toggle.
  Thermal indicators and fit pressure ranges are checked against every gold record.
- Layout checks cover 1440×1000, 1000×668 and 800×600 at both text sizes, including
  visible selected records/footer actions and no horizontal record-table scrolling.
- The scoped native smoke passes for the simplified columns, absence of the inspector,
  documentation links, held/no-hit states, fixed material-pane height, source thermal
  and pressure values, stable sorted identity and real loading;
  the detached Phase Editor checks and processing-child cleanup also pass. It was
  built with an isolated Cargo target while the user's live preview kept running.
- Prior combined model verification: 241 desktop Python tests passed (5 skipped).
  The catalog contract was compared with Qt for all 233 materials / 678 records.
  Python/scientific source code has not changed in this simplification.

## Limits

- React opens All and lists diffraction-capable materials only; Qt initially opens
  Recent and can also show EoS-only entries.
- Recent/favourite IDs are preview-local and separate from Qt's INI settings.
- Dialog size resets on reopening. The Qt vertical splitter is not reproduced.
- External documentation URLs are resolved from the selected bundled record.
  Automated tests mock external browser launch and do not establish website
  availability or Windows/Linux native behavior.

# EoS Material Database explorer

Current interface, simplified on 2026-11-04 after feedback on information overload.
The browser is a material/record picker. Full scientific documentation is reached
through the selected record's Peritheos and reconstruction-report links.

## Visible workflow

- Search by material name, formula or alias, using the existing ranked model search.
- Choose from Recent, Favourites or All, optionally limited to diffraction data.
- Select a material, then its record. The record table begins with author/year,
  followed by the EoS type. A variant column appears only for materials whose
  records contain otherwise ambiguous author/year/type combinations.
- Variant names retain catalog wording; repeated citation prefixes are removed.
  Full record labels remain available on hover. Rows stay one line high.
- Load the selected record or export the material with all its records.
- Open Peritheos or the reconstruction report for scientific detail.

The browser no longer shows assessment/source tabs, parameter tables, raw JSON,
pressure/volume/modulus columns, long assessment text, material notes or a permanent
explanatory legend. It uses two separated lists in a smaller resizable dialog,
with persistent footer actions and no horizontal record-table scrolling.

Held defaults still require an explicit record selection. Unavailable diffraction
data and source-only records still block loading. These states show one brief
notice; the complete model reason remains in its tooltip. The existing tetragonal
CaSiO3 approximation requires an explicit opt-in and displays a short approximation
notice, with the complete model note available on hover.

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
  model loading/export and explicit assumptions.
- Layout checks cover 1440×1000, 1000×668 and 800×600 at both text sizes, including
  visible selected records/footer actions and no horizontal record-table scrolling.
- The scoped native smoke passes for the simplified columns, absence of the inspector,
  documentation links, held/no-hit states, stable sorted identity and real loading;
  the detached Phase Editor checks and processing-child cleanup also pass. It was
  built with an isolated Cargo target while the user's live preview kept running.
- Prior combined model verification: 241 desktop Python tests passed (5 skipped).
  The catalog contract was compared with Qt for all 233 materials / 678 records.
  Python/scientific source code has not changed in this simplification.

## Limits

- React opens All with the diffraction filter enabled; Qt opens Recent with it off.
- Recent/favourite IDs are preview-local and separate from Qt's INI settings.
- Dialog size resets on reopening. The Qt vertical splitter is not reproduced.
- External documentation URLs are resolved from the selected bundled record.
  Automated tests mock external browser launch and do not establish website
  availability or Windows/Linux native behavior.

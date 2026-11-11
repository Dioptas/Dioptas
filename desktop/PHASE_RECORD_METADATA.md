# Native EoS publication record editing

The Phase Editor’s **Equation of state → Publication record** section provides a
structured citation editor, publication uncertainties/fixed flags, experimental
and validity ranges, reference temperature and record notes. A short citation is
visible while collapsed. Less-used citation fields and parameter metadata are
progressively disclosed. Stored coefficients appear beside their reported
uncertainty and publication-fixed checkbox; coefficient editing remains in the
existing parameter controls. Model choices, record labels and default-record
controls retain their established behavior.

Publication errors and fixed flags describe the source record, independently of
live fit constraints or new uncertainty estimates. Signed finite reported errors
are retained without assigning a confidence level or changing any recorded
uncertainty convention. Values, including optional/null thermal coefficients,
are never reconstructed by the metadata command.

## Draft and ownership behavior

- One Apply/Cancel boundary covers publication fields. Ctrl/Command+Enter applies
  the draft. Validation opens the relevant disclosure and focuses the invalid
  field; backend failures retain the draft for correction or cancellation.
- Pending drafts block record/model changes, material reload/copy/save and editor
  closing. Native close/retarget events are guarded synchronously after input.
  External refreshes wait until the draft ends. Cancel reloads the actual record.
- Requests identify the phase by UID, the selected record index, and an opaque
  backend-generated record token. Concurrent changes reject the draft atomically;
  no whole-record JSON is round-tripped through JavaScript for editing.
- Bundled sources remain read-only. **Edit a copy** produces an independent,
  unvalidated user material. Editing an already validated user-owned record defers
  its validation and retains the original audit and unknown audit fields.
- Updates modify only explicitly changed metadata fields. Unknown fields,
  unsupported parameter metadata, source attribution, dataset/record links,
  labels/defaults and other records remain intact.

## Stored fields and clearing

| Field | Storage and blank/clear behavior |
| --- | --- |
| Authors | `reference.authors`; semicolon-separated input becomes an author list; blank removes the field. |
| Truncated authors | `reference.authors_truncated`; unchecked removes the flag. |
| Year | `reference.year`; integer 0–9999; blank removes it. |
| Journal/source, volume, pages/article, DOI, details | `reference.source`, `volume`, `locator`, `doi`, `details`; blank removes only the edited field. |
| Free-text references | Unedited strings remain strings. Editing structured fields retains an existing string in `reference.details`. An empty structured reference becomes `""`. |
| Experimental P/T | `experimental_pressure_range_gpa`, `experimental_temperature_range_k`; ordered finite pairs, or both blank to remove. |
| Validity P/T | `validity.pressure_gpa`, `validity.temperature_k`; distinct from experimental bounds; removing bounds retains other validity metadata. Temperatures must be nonnegative. |
| Reference temperature | `temperature_ref`; finite, nonnegative K; blank removes it and uses the model’s default. This reference state may change phase-volume predictions. |
| Notes | `notes`; blank removes it. |
| EoS uncertainties/fixed | Record-level `parameter_errors` / `fixed_parameters`; a cleared error is explicit null; unchecking removes only that parameter from the fixed list. |
| Thermal uncertainties/fixed | Same fields inside `thermal`; independent of EoS fields with the same name. |

The numerical engine requires both authors and year for a structured citation.
Qt/user records permit either to be unknown. The native engine adapter converts
partial citations to supported free text **only in the disposable numerical
input**. Authored EOSMAT and current native format-2 `.dio` documents retain the
complete structured citation and unknown fields. No author or year is invented.

Metadata-only changes do not recalculate the phase or rebuild pattern products,
refit, integrate detector pixels, or change coefficient values. An explicit
reference-temperature change recalculates the selected phase’s predictions and
rolls back if that evaluation fails; detector processing remains unchanged.

## Verification

From `desktop`:

```sh
cargo test --locked --manifest-path backend/Cargo.toml --all-features
cargo clippy --locked --manifest-path backend/Cargo.toml --lib --bins -- -D warnings
npm test
npm run build
npm run test:phase-metadata
npm run test:ui-components
```

Native round-trip tests cover every edited field, clearing/partial citations,
EOSMAT save/reload, `.dio` save/reopen after source removal, independent records,
record copies, labels/defaults, source protection, stale selection, failure
rollback, unknown metadata (including integers above JavaScript’s exact range),
null coefficients, and unchanged detector/cake/pattern products. The full native
suite passes; two pre-existing external-image tests remain ignored.

The Rust-backed headless Chromium/WebKit workflow covers interaction, validation
focus, keyboard Apply, injected failure recovery, stale-draft cancellation,
long citations, and 900/1000/1440 px layouts at normal/larger text. The detached
editor’s Tauri event contract is tested headlessly against the actual Rust stdio
processor with mocked window/event APIs: close/retarget protection and deferred
refresh pass. This is not a native OS-window campaign. Screenshots and receipts
are in ignored `desktop/artifacts/phase-metadata/`.

Production-library/binary Clippy passes with warnings denied. The all-target
variant encounters the pre-existing `items_after_test_module` warning in
`phases.rs`; this feature leaves that unrelated test placement unchanged.

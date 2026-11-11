# Phase Editor GUI workflow tests

Run from `desktop`:

```sh
npm run test:phase-editor-workflows
```

This command builds the current Rust worker and frontend, then runs the complete
built application headlessly in Chromium and WebKit. Tests use independent
workers, a real calibrated detector image, and a bundled Gold structure copied
through the GUI. Temporary EOSMAT files and test workers are cleaned up. User
windows, files and live worker sessions are not used.

The same suite is included in `npm run test:ci-native`'s UI gates.

## Covered workflows (16 per browser)

1. Published material stays read-only; Edit a copy creates an independent
   editable structure with atomic sites and reflections retained.
2. Cancel and Escape dismiss clear-all confirmation without changing records.
3. Confirming clear-all removes every EoS, preserves lattice/atoms/reflections,
   disables actions requiring a record, and leaves Add available.
4. A material with no EoS can be saved and reloaded; Add then creates a valid
   record with K0 = 100 GPa.
5. Empty, nonnumeric, infinite and negative modulus drafts cannot be saved;
   Escape restores the accepted value without changing the model or file.
6. Zero modulus passes text parsing but is rejected by the engine; the editor
   restores the previous model, shows the error and accepts a subsequent edit.
7. Rapid Enter/Tab sends one commit; Close waits for a deliberately delayed
   command and reopening shows the exact accepted value.
8. Duplicate, switch and set default maintain independent records; cancel
   deletion preserves them; confirmed deletion selects the remaining record.
9. Deleting the last EoS permits creating another valid 100 GPa record.
10. Model changes update the displayed equations; the unsupported sound-velocity
    choice remains disabled; Dewaele beta = 0 rolls back cleanly.
11. Custom Cvmax can be cleared to the 3nR convention; q = 0 is accepted.
12. Adding/clearing double-Debye Tr changes the displayed reference convention;
    clearing optional numeric coefficients displays the applied defaults.
13. Cancelled Save As leaves filename/model intact; Save applies an outstanding
    numeric draft before writing; Save As and Reload preserve exact parameters.
14. Phase editing leaves detector pixels and integrated arrays unchanged while
    updating the edited phase's plot markers. The published source stays intact.
15. A fresh Rust process and reloaded application reproduce the saved EOSMAT,
    structure, model controls and help preference under the same calibration.
16. GUI pressure/temperature changes respectively compress/expand the calculated
    volume, and the reopened editor displays that result.

Clearing all records deliberately changes the displayed V0 from the former
record's fitted volume to the volume calculated from the retained lattice.
The tests preserve the six lattice parameters, atomic sites and reflection
coordinates, rather than treating these two V0 definitions as interchangeable.
Reflection comparisons across worker restarts use the same detector calibration,
wavelength and integration settings.

## Regression found and fixed

Clearing an optional coefficient whose concrete default was already active
could leave a blank input even though the model held the default (for example
Ve = 1). The Phase Editor now supplies numeric defaults from constructor metadata
to its field editor so Enter/blur display the accepted default consistently.
Tr and Cvmax retain their meaningful blank/unset conventions.

## Evidence and limits

`artifacts/phase-editor-workflows/validation.json` records each passed workflow;
completed screenshots and failure screenshot/HTML are written alongside it.
All 16 workflows pass in both browsers (32 workflow runs), with no page errors.
The existing model-help, publication-metadata and unit checks are separate gates.

Only the OS file chooser is replaced with deterministic temporary paths and a
cancellation result. All edits, confirmation dialogs, serialization, reloading,
model calculation and plot data use the real app and Rust worker. This suite
does not qualify native OS dialog behavior or prove scientific correctness at
all states; see `PHASE_EQUATION_AUDIT.md` for the numerical/source audit.

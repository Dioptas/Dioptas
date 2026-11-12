# Native previous-session recovery

The Rust/Tauri app offers **Restore** and **Start fresh** after opening its
workspace whenever its automatic recovery file exists. Escape chooses Start
fresh. Restoring does not delete or consume the checkpoint, so subsequent
ordinary launches offer the choice again. Closing before choosing preserves it.

The Qt reference is `MainController.save_default_settings()`,
`load_default_settings()` and `setup_backup_timer()`. Its default directory is
**`~/.Dioptas`** (capital D), with a whole-project `config.dio`, separate working
directories, and a ten-minute dirty-only backup timer. Qt's project saves the
selected configuration, configuration parameters, cached detector data, masks,
calibration, corrections, patterns, overlays, phases, map data and model-owned
view parameters (`img_mode`, docking/layout and calibration convention).

## Native storage and ownership

The native checkpoint is **`recovery/native-session-v1.dio` under Tauri's
application-data directory**, resolved through the application's identifier.
`DIOPTAS_RECOVERY_DIRECTORY` overrides the containing directory for isolated
testing. Smoke/example modes and the explicit Python comparison backend disable
native recovery. This implementation never probes, overwrites, migrates or
consumes Qt's `~/.Dioptas/config.dio` or `working_directories.json`.

The checkpoint uses the existing owned-data native format-2 project writer.
Its `native_recovery` record stores version 2, the explicit user-project path
(or null for unsaved work), bounded renderer display settings, and a generation
reference for the separate undo/redo companion. Version-1 checkpoints remain
readable and restore without history. Science and
metadata publish together: a private sibling file is written and flushed,
file handles are closed, the staged file is synced, and it atomically replaces
the destination. Errors or cancellation before publication retain the previous
file. There is no in-place metadata update after publication.

Saving recovery does not set or change the current user-project path or touch
that project's bytes. Restoring reinstates its original identity. Ordinary
explicit project saves remove the private recovery record, including after a
recovery restore. A normal project or Qt recovery file is not implicitly
accepted as a native recovery checkpoint.

## Undo/redo recovery

Automatic recovery also saves mask Undo/Redo and the interleaved calibration/
integration Undo/Redo timeline for **every configuration**, including inactive
ones. These steps live in a hidden sibling
`.dioptas-recovery-history-<unique>.h5` file. **Ordinary user-saved `.dio` projects
still contain no undo history**, even when saved after restoring a session.

The existing development handoff's shared-object serializer now works in release
builds too. It stores shared planes, curves and history entries once, preserving
floating-point bits and reconstructed object identity. Recovery retains the
current model heads along with the history, preserving comparisons and the
chronological order of subsequent edits. Restored steps cannot turn automatic
exports or acquisition watchers back on.

History has a **128 MiB serialized-data budget**, plus at most 16 MiB of file
overhead. Object count, nesting and read allocations are also bounded. If the
budget is exceeded, recovery progressively removes the farthest Undo/Redo steps
while retaining a continuous nearest timeline. If even the smallest history is
too large, applied work still saves with history omitted. Restore reports how
many steps were retained/omitted. The in-memory history of the running session
is not trimmed by saving recovery.

The new history generation is fully staged and synced before the core checkpoint
atomically references it. Failed/cancelled core publication removes the new
generation and retains the previous checkpoint/history pair. Successful saves
remove the superseded companion. A crash between publishing the companion and
publishing the core can leave an unreferenced companion; it cannot invalidate
the previous pair. A missing, corrupt or mismatched referenced companion causes
a clear restore error and leaves the live session and existing files untouched.
Keep both files together when manually copying recovery data.

Single-crystal XRD recipes, derived results and its independent edit history
remain outside powder `.dio` recovery. If closing from that mode, powder recovery
opens in Calibration; save the single-crystal recipe through its own controls.

## Preserved state and startup behavior

- All configurations and their active selection, calibration and picked groups,
  detector/orientation, masks, image corrections, integration options, working
  directories, embedded detector pixels and project-owned patterns/overlays,
  phases, Batch and Map data use the existing native project persistence.
- Renderer recovery retains the current mode, calibration step/convention,
  image/cake choice, configuration-toolbar visibility, ring/picking controls,
  current independent detector/cake limits, log choices and palettes, histogram
  preferences, pattern square-root choice, corrected-image choice and cake shift.
  It validates these fields before applying them and refreshes scientific drafts
  from the restored applied settings.
- Original image files may be unavailable: embedded pixels restore offline, with
  a notice listing unavailable configuration image sources. Navigation/reload
  still requires the originals. If required project data/resources cannot load,
  recovery fails clearly and atomically without partially replacing the session.
  If scientific restore succeeds but displaying it fails, the UI reports that
  distinction and asks for a restart instead of offering a misleading fresh
  workspace while restored data remain in the processor.
- Acquisition watchers and automatic exports remain off on restore and through
  recovered Undo/Redo, as on normal project open. Unapplied numeric drafts, transient plot
  zoom/hover/click state, detached-window contents and inactive configurations'
  renderer-only contrast memories are not checkpointed. Existing persistent app
  preferences and companion-window placement retain their own storage.
- Positional paths and `--project`, `--image`, `--calibration` (separate argument
  or `=path`) are opened in order and suppress the recovery prompt. `.dio` and
  `.poni` positional paths select the corresponding loader. macOS file-open
  events also take priority, including events received after the first prompt.
  An unsuccessful explicit startup cannot replace the old checkpoint with an
  unchanged blank workspace.

## Backup, close and failure handling

The host checks every ten minutes and saves only after a scientific revision or
captured display setting changes. It reads revision metadata without preparing
detector display buffers. Startup probes do not read/deserialize a potentially
large recovery archive. Actual restore, backup and close serialization run on
blocking workers, leaving the event loop responsive.

Normal main-window close and application Quit stop admitting new mutations,
drain already admitted commands, and save before allowing exit and shutting down
the processor. Progress/cancellation remain out of band. A close-save error offers
**Retry** or **Close without saving** and preserves the old file. Timer failures
surface in the UI. A failed restore retains the file and offers retry or Start
fresh. After failed restore, closing an unchanged fresh workspace preserves that
file; making new scientific changes enables the next checkpoint. A deliberate
Start fresh without a failed restore saves the fresh workspace on normal close.

## Verification

- `backend/tests/integration/recovery.rs`: restart with missing originals, embedded pixels,
  multiple configurations/settings, user-project identity and unchanged project
  bytes, unsaved identity, ordinary-save metadata removal, corrupt/non-recovery
  input rollback, and failed/cancelled writes retaining the previous file.
  Also checks mask and interleaved scientific Undo/Redo across configurations,
  new-edit chronology after restart, and history-free ordinary projects.
- `project/recovery_history.rs` and `history_transfer.rs` unit tests cover size
  trimming, retained nearest steps, complete history omission, shared identity
  and nonfinite float bits, cancellation/read bounds, version-1 compatibility,
  missing/corrupt companions, failed publication cleanup and automation remaining
  disarmed through recovered Undo/Redo.
- Host `recovery::tests`: native child restart/restore, clean close checkpoint,
  idle-backup suppression, decline/fresh close, failed-recovery protection,
  explicit startup priority, and draining admitted work before shutdown.
- `npm run test:session-recovery`: real Rust processing behind headless Chromium
  and WebKit, each testing Restore, Start fresh, failed recovery, failed display
  after scientific restore, and explicit startup. Checks focus, restored display settings, offline-source notice,
  scientific/project identity, another checkpoint/restart and unchanged source
  recovery bytes. Screenshots and receipts go to ignored
  `desktop/artifacts/session-recovery/`.
  The Restore scenario exercises the actual Undo/Redo buttons in Integration
  and Mask after a real worker restart with the original image removed.

Tests use temporary HOME/app-data or explicit temporary recovery directories.
No installed app, real user recovery file or visible native window is used.
Native OS close/dialog presentation and Windows/Linux application-data behavior
still require platform qualification; no new installer/release is published by
this change.

Validated on November 12, 2026: production build, 178 frontend unit tests,
seven native project/recovery model tests, five recovery host tests, ten recovery
browser scenarios, existing native project UI regressions in Chromium/WebKit,
and Clippy with warnings denied for the recovery model target. Backend build/test
commands used `MACOSX_DEPLOYMENT_TARGET=14.0` and `CARGO_INCREMENTAL=0` in the
isolated checkout.

The history follow-up also passes the four recovery integration tests in both
debug and optimized release builds, four history lifecycle/limit tests, two
shared-serializer tests, the existing five project model tests, five host tests,
and all ten headless recovery scenarios with real Undo/Redo interactions.
The production UI build, 178 frontend tests and all-target native Clippy with
warnings denied pass. Verification continues to use only temporary recovery
directories and headless windows.

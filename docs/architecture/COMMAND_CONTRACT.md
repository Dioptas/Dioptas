# Native command execution contract

`contract/src/command_contract.rs`, in the `dioptas-contract` crate, is a
dependency of both the Tauri host and the Rust processor. It is the source of
truth for the request-frame byte limit and execution policy.
Scientific payloads/results retain their existing JSON protocol. React invokes
Tauri's `desktop_invoke`; the host forwards requests over its owned processor
stdio connection and returns metadata plus binary raster buffers through Tauri.

- `OutOfBand` commands are progress and cancellation. They bypass the host's
  ordinary command/swap gate.
- `Cancellable` commands can load or recalculate scientific data. One `Control`
  owns queued cancellation and running progress for the whole command, including
  nested dispatch to another command. New loading/processing entry points belong
  here even when they delegate to `open_image` or `integrate` internally.
- `Ordinary` commands are short metadata/readout work. They do not restart a
  completed progress indicator. An unrecognized command retains the processor's
  normal unsupported-command error.

Cancellation remains cooperative: individual native library calls finish before
the next cancellation check. The registry does not add rollback to commands that
do not already provide it.

## Optional metadata product reuse

The wire envelope accepts an optional `cachedProducts` object containing the
client's `batch` and/or `map` content tokens. It is separate from scientific
command arguments. Omission retains legacy full responses; an empty object
opts into product descriptors without advertising any cached state.

Opted-in response headers include `products`, mapping each included product to
its content token and full JSON byte length. A product whose exact JSON matches
the advertised token is omitted from the wire result. Changed products and
explicit nulls receive new tokens and are sent in full. Other result fields and
the binary raster framing retain their existing meanings.

Each RasterTransfer owns a bounded metadata cache and pins advertised product
objects and their raster bytes per request, including during concurrent cache
replacement. It restores referenced products before returning the ordinary
typed result, so callers see the same complete fields and immutable buffer
identities. Unknown or unadvertised references fail explicitly. Cache charging
includes retained binary packet owners; oversized products keep full transfer.

Tokens hash all metadata fields without an encoded temporary copy. This removes
repeated transfer and frontend reconstruction of unchanged products. Native
snapshot construction and content hashing still visit their metadata; this is
not a claim that those remaining costs are constant in series size.

The 16 MiB frame limit includes UTF-8 encoding, JSON escaping, metadata and the
terminating newline. The host checks the encoded frame before registering a
pending reply or writing any bytes, so a large figure/export is a recoverable
command error and leaves the scientific child and unsaved session intact.

The processor also rejects oversized direct-client requests without exiting.
It retains at most one bounded frame prefix, drains the rest through the newline,
and returns an error. A structurally parsed top-level request id in the first
64 KiB correlates that error; clients should put `id` before `payload`, as the
native clients do. A malformed request without an early id gets an id-0 error.
Parsing never searches payload strings for an apparent id. Later frames and
the scientific session remain usable. An unterminated oversized frame is drained
to EOF and rejected before normal shutdown.

The shared source participates in development backend watching. Tests cover the
execution classification, bounded routing/draining, oversized-frame recovery,
host rejection with the same live child and unsaved configuration, and real
transfer-processing cancellation with full state restoration.

## Frontend command ownership

`src/commandCoordinator.ts` owns workspace command admission, ordered execution,
interactive reservations and release after completion or failure. A reservation is
released in `finally`, including when a queued command becomes obsolete or its
identity predicate throws.

The coordinator distinguishes applied, cancelled, deferred, failed and skipped
outcomes. Deferred commands include image/calibration changes and HDF5 source
decisions; they have not yet applied the requested mutation. Busy admission and
superseded contexts are separate skip reasons. Existing `IntegrationRun`
callbacks remain compatible while callers gradually adopt typed outcomes.

Queued overlay commands use stable UIDs, resolved by the processor at execution.
An explicitly missing UID is rejected rather than redirected to an array index;
index-only commands remain available to explicit compatibility clients. Undo
grouping uses the same identity. The headless ordering check holds a response
while later move, edit and removal actions are captured, exercising both browser
engines against the real native processor.

The frontend scheduling policy describes UI admission and quiet edits; the
shared Rust registry describes native execution and cancellation. These are
different responsibilities. Scientific arrays continue through the existing
binary raster boundary.

## Structural request DTOs and response metadata

`command_payload_schema.json` generates both
`src/nativePayloadContracts.generated.ts` and
`contract/src/native_payload_contracts.generated.rs`. Run
`node scripts/generate_native_contracts.mjs` after changing this schema;
`--check` verifies committed generation without changing files or requiring a
compiler. The frontend registry imports these payload types instead of defining
a second copy.

Native structural DTO coverage is deliberately incremental: pixel and peak
coordinates, source/frame navigation, transfer/flat/image-background edits,
configuration selection/operations/browsing, combination settings, worker count,
cake-profile extraction/export, and the host HDF5 companion chooser metadata.
The schema is the exact field-level coverage ledger. A field marked
`validate:false` retains a tolerant legacy handler or host-metadata path. The
frontend type still describes the intended typed input; the native layer does
not turn a formerly ignored alternative-operation field into a new error.

`wire_contract::validate_payload` runs at the Tauri chooser boundary, before a
host writes a request, and in the processor's `Request::validate`. Generated
serde DTOs borrow strings from the existing JSON object. Native `*Fields` types
check **present field types**, while existing handlers still own missing fields,
numeric ranges, defaults, cross-field constraints and unknown-field rules.
Numbers are checked as numbers without coercing the original JSON value or
narrowing fractional/negative inputs before the scientific handler. Operation
variants select their relevant fields before checking them. Common
`requested_products` keeps its existing strict validation and error.

This does not claim that every Rust scientific handler has been converted to a
fully typed command. Uncovered commands return `PayloadCoverage::Legacy` and
retain their existing dispatch and explicit unsupported-command errors. Neither
this validator nor the generated types introduce a transport, server, alternate
processor, or fallback.

Success, error, chooser cancellation and image/calibration/HDF5 decision replies
use shared metadata constructors with the existing wire field names. Deferred
decision objects are moved into their envelope. The additive borrowed
`ResponseMetadata` view classifies HDF5/image/calibration deferrals before failure
or cancellation, including deferred replies that also contain `cancelled:true`.
Optional failure/cancellation fields remain optional. It reads a fixed set of
top-level metadata fields and does not traverse, copy or reconstruct scientific
arrays or raster buffers. The full scientific result remains in its original
object; binary packet framing and content-addressed cache identities are unchanged.

Tests cover generated-file drift, malformed present fields, missing chooser paths,
numeric and request round trips, explicit legacy dispatch, borrowed string and
decision storage, response precedence, unchanged binary framing, and a real host
session remaining usable after rejected structural input. The development watcher
also observes shared schema, generator and generated Rust changes.

## Frontend payloads and results


`src/commandContracts.ts` maps frontend command names to payloads and result
fields. `Invoke`, `Run` and request-reader APIs retain the relationship between a
command and its payload through correlated argument tuples. Command-specific
success fields are distinct from failures, cancellations and deferred decisions.
HDF5, image and calibration decisions take precedence over cancellation because
existing deferred replies can also contain `cancelled: true`.

Detached Batch/Map messages use the same correlated command types.
`src/windowCommandRpc.ts` owns request-id correlation, pending-request cleanup
and the decode assertion at that IPC boundary. Edit replies contain only an
acknowledgement; scientific data arrives through the existing refresh/snapshot
path. Local `batch_hide` remains a window action outside the scientific registry.

## Response ownership

`src/responseSnapshot.ts` owns the pure transition for processor-owned session,
detector, pattern, cake, Batch and Map data. Its hook publishes that model to
React. `src/workspaceResponse.ts` applies synchronous canonical-source refs and
coordinates display preferences, inspection and workspace effects through named
domain ports. Canonical backend state remains separate from the rendered
pattern-only state, which retains existing detector geometry and option drafts.

`src/commandResponse.ts` owns the response transaction: deferred dialogs,
stored-map fallback, linked-position and Auto-level preparation, publication,
completion effects/callbacks, and state refresh after errors. `App.tsx` composes
these owners with the coordinator and the existing UI. Preparation and callbacks
remain inside the command reservation. Omitted products retain prior data;
explicit null clears the nullable products that already support it. Immutable
buffer identities and scientific arrays continue through the existing binary
raster implementation without copies introduced by response application.

# Native command execution contract

`command_contract.rs` is compiled into the Tauri host and Rust processor. It is
the source of truth for the request-frame byte limit and execution policy.
Scientific payloads/results still retain their existing JSON protocol; this
registry is the first step toward typed command schemas, not a new transport.

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

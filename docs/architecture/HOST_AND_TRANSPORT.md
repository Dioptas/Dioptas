# Host, processor and binary transport

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

## Live processor reload

Rust processor source/Cargo/data changes rebuild the worker in the background.
After a successful build, the host waits for the current operation, checkpoints
all configurations into a private owned-data project, restores the new worker,
and swaps the stdio connection. The window stays open: images, masks, corrections,
geometry, calibration drafts/picks, file settings, combined results, configuration
identities/selection, linked inspection and the current project save path survive.
The frontend refreshes results without resetting plot views or its unapplied drafts.
Build/start/restore failures keep the old worker and its session active. Progress
and cancellation remain available while a reload waits for an operation.
Mask, calibration and integration Undo/Redo stacks survive worker replacement,
including their chronological order and each configuration’s redo branches.
History data is held in a private binary sidecar with shared arrays stored once;
it is not added to ordinary saved projects. The first update from an older
worker that cannot export history initializes empty stacks once. Reload status and
build errors appear in the footer and launcher log. Set `DIOPTAS_DEV_RELOAD=0` to
disable the watcher. Generated build/staging files are excluded from UI and host
watchers, so a scientific rebuild does not reload the window.

## Host and processor boundary

`src-tauri/` contains the Rust host. React calls one Tauri command, which sends
requests over stdin/stdout to a local `dioptas-processor` Rust process. Native
file dialogs belong to Tauri. There is no scientific HTTP/API server or remote
service. The bundled frontend uses the Tauri asset protocol, without Vite.
The command worker owns the mutable scientific session. Bulk Batch/Map execution
lends one immutable reader and Dioptrin plan to scoped frame workers; each owns
its decoder buffers and float64 accumulators. Ordered collection and publication
stay on the command worker. Progress and cancellation bypass that
worker without accessing native objects. Pipe responses carry request IDs so a
long fit does not block progress/cancel responses. Window closure drops the pipe,
cancels pending refinement and reaps the child, with a bounded kill fallback.

Native image transfer uses binary buffers through
Tauri IPC. Commands and metadata remain JSON. Detector, mask, cake and map
pixels never become base64 strings on this path. A response contains a
little-endian uint32 header length, the UTF-8 JSON header, then the raw buffers
listed in that header. Buffer IDs identify immutable content; the window
advertises the IDs it still retains so unchanged pixels need not be resent.

The window retains up to 128 MiB of
binary buffers. Detector and cake views normally render with WebGL 2; the
Canvas fallback and PNG export share a 96 MiB colour-image cache. Both caches evict older
entries. Render keys include mask content, palette, linear/log scaling and
intensity limits. Pending requests keep their advertised buffers alive even if
another response evicts them. Ring contours are reused only while the angular
array and calibrant angles agree; integrations continue to use the current
scientific models. Headless browser drivers use a Node adapter for the native
processor, with JSON/base64 only at the browser-test boundary.

import type { CommandResult } from "../../src/commandContracts";
import type { Response } from "../../src/types";

// These shapes mirror existing native response sites. Keep cancellation and
// multifile exports represented even when no UI caller reads their fields yet.
const multifile = { ok: true, savedPaths: ["sample_000.xy"], exportedFrames: 1 } satisfies CommandResult<"integration_save_batch">;
const singleFile = { ok: true, savedPath: "sample.h5" } satisfies CommandResult<"integration_save_batch">;
const closedWindow = { ok: false, cancelled: true } satisfies CommandResult<"state">;
declare const imageDecision: NonNullable<Response["imageChange"]>;
declare const hdf5Decision: NonNullable<Response["hdf5SourceRequest"]>;
const imageDeferred = { ok: true, cancelled: true, imageChange: imageDecision } satisfies CommandResult<"open_image">;
const hdf5Deferred = { ok: true, cancelled: true, hdf5SourceRequest: hdf5Decision } satisfies CommandResult<"open_image">;
const batchImages = { ok: true, savedPaths: ["one.tif"], imageBatchSaved: true } satisfies CommandResult<"open_image">;
const emptyMapLevels = { ok: true, mapLevels: null } satisfies CommandResult<"map_levels">;
const emptyBatchLevels = { ok: true, batchLevels: null } satisfies CommandResult<"batch_levels">;
void [multifile, singleFile, closedWindow, imageDeferred, hdf5Deferred, batchImages, emptyMapLevels, emptyBatchLevels];

// @ts-expect-error A successful non-cancelled state reply must include state.
const missingState: CommandResult<"state"> = { ok: true };
void missingState;

declare const exported: CommandResult<"integration_save_batch">;
if (exported.ok && !exported.cancelled && !exported.imageChange && !exported.calibrationChange && !exported.hdf5SourceRequest) {
  // @ts-expect-error A multifile export need not return a single savedPath.
  const path: string = exported.savedPath;
  void path;
}

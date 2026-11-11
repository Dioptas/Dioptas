import type { WindowCommandRequest, WindowRun } from "../../src/windowCommandRpc";
import { WindowCommandRpc } from "../../src/windowCommandRpc";

declare const rpc: WindowCommandRpc;
declare const run: WindowRun;
rpc.read("map_levels", { clipping: 0.1 });
rpc.edit("integration_save_batch", { format: "xy" });
rpc.edit("batch_hide");
run("batch_hide");

// @ts-expect-error A local window action is not a scientific read command.
rpc.read("batch_hide");
// @ts-expect-error Export formats remain constrained across the detached boundary.
rpc.edit("integration_save_batch", { format: "unknown" });
// @ts-expect-error Required native command arguments remain required in windows.
run("batch_unit");
// @ts-expect-error The window envelope preserves the command/payload relation.
const invalid: WindowCommandRequest = { type: "request", id: "r", command: "batch_unit", args: { index: 2 }, read: false };
void invalid;

async function edited() {
  const acknowledgement = await rpc.edit("integration_save_batch", { format: "xy" });
  // @ts-expect-error An edit acknowledgement does not contain a saved-path result.
  acknowledgement.savedPath;
  const result = await rpc.read("map_levels");
  if (result.ok && !result.cancelled && !result.imageChange && !result.calibrationChange && !result.hdf5SourceRequest && result.mapLevels) {
    const levels: [number, number] = result.mapLevels;
    void levels;
  }
}
void edited;

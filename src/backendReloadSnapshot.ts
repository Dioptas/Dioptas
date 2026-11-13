import type { Invoke } from "./commandContracts";
import type { Response } from "./types";

/** Reconcile each scientific workspace with the worker that actually survived
 * the update. An omitted SC snapshot must never leave an obsolete image live. */
export async function refreshBackendSnapshots(
  invoke: Invoke,
  apply: (result: Response) => void,
  hadCrystalScan: boolean,
  restored: boolean,
): Promise<boolean> {
  if (restored) {
    const result = await invoke("state");
    if (!result.ok)
      throw new Error(result.error || "Cannot refresh the updated processor.");
    apply(result);
  }
  const crystal = await invoke("scxrd_snapshot");
  if (!crystal.ok || !crystal.scxrd)
    throw new Error(crystal.error || "Cannot check the rotation scan.");
  apply(crystal);
  return hadCrystalScan && crystal.scxrd.frames === 0;
}

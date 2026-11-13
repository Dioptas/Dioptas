import type { Invoke } from "./commandContracts";
import type { Response } from "./types";

export const lostCrystalScanMessage =
  "Reopen the rotation frames to continue. An earlier backend update lost the loaded scan; your original files are unchanged. Save your work before restarting to adopt the backend update.";

export function backendUpdateMessage(message: string): string {
  return message.replace(
    /^Backend update failed; current session retained\.\s*/,
    "",
  );
}

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

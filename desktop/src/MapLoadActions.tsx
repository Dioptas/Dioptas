import { FolderOpen } from "lucide-react";
import type { MapRun } from "./mapDomain";

/** The same source actions are available beside the points and in an empty map. */
export function MapLoadActions({
  ready,
  calibrated,
  run,
  empty = false,
}: {
  ready: boolean;
  calibrated: boolean;
  run: MapRun;
  empty?: boolean;
}) {
  return (
    <>
      <button
        className="plot-tool-button"
        aria-label={empty ? "Load images to build a map" : "Load images…"}
        title="Load detector images"
        disabled={!ready || !calibrated}
        onClick={() => run("map_load", {}, "Integrating map images…")}
      >
        <FolderOpen size={15} /> Load…
      </button>
      <button
        className="plot-tool-button"
        aria-label={empty ? "Load a folder to build a map" : undefined}
        title="Integrate detector images from a folder"
        disabled={!ready || !calibrated}
        onClick={() => run("map_folder", {}, "Integrating scan folder…")}
      >
        Folder…
      </button>
    </>
  );
}

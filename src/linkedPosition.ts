import { radialValues } from "./radialReadout.ts";
import type { Invoke, Response, Unit } from "./types";

export type PatternPosition = { x: number; unit: Unit };

/** One physical position, rendered in each pattern's own radial display unit. */
export function patternPositionInUnit(
  linked: Response["linked"],
  local: PatternPosition | undefined,
  unit: Unit,
  wavelength?: number,
): number | undefined {
  const source = linked
    ? { x: linked.twoTheta, unit: "2th_deg" as const }
    : local;
  if (!source) return;
  const position = radialValues(source.x, source.unit, wavelength)[unit];
  return position != null && Number.isFinite(position) ? position : undefined;
}

/** Restore the physical inspection after loading a different scan image/frame.
 * Run inside the image-selection queue so contours belong to the new detector.
 */
export async function restoreMapPosition(
  invoke: Invoke,
  result: Response,
  selected: Response["linked"],
): Promise<Response> {
  if (
    !selected ||
    result.linked ||
    !result.state?.hasImage ||
    !result.state.calibrated
  )
    return result;
  // Cake inspection accepts physical 2θ, independent of the Integration unit.
  const restored = await invoke("validation_position", {
    source: "cake",
    x: selected.twoTheta,
    ...(selected.azimuth == null ? {} : { azimuth: selected.azimuth }),
  });
  if (!restored.ok)
    throw new Error(
      restored.error || "Could not restore the selected diffraction position.",
    );
  return { ...result, linked: restored.linked };
}

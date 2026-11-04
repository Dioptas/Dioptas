import { radialValues } from "./radialReadout.ts";
import type { Response, Unit } from "./types";

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

import { radialValues } from "./radialReadout.ts";
import type { Pattern, Unit } from "./types";

/** Move the complete display together; scientific map coordinates stay stored. */
export function mapPatternInUnit(
  pattern: Pattern,
  unit: Unit,
  wavelength?: number,
): Pattern {
  if (unit === pattern.unit) return pattern;
  const xValue = (x: number) => radialValues(x, pattern.unit, wavelength)[unit];
  const samples = (curve: { x: number[]; y: (number | null)[] }) => {
    const converted = curve.x
      .map((x, i) => [xValue(x), curve.y[i]] as const)
      .filter(
        (point): point is readonly [number, number | null] =>
          point[0] != null && Number.isFinite(point[0]),
      );
    return {
      x: converted.map((point) => point[0]),
      y: converted.map((point) => point[1]),
    };
  };
  return {
    ...pattern,
    ...samples(pattern),
    unit,
    curves: pattern.curves?.map((curve) => ({ ...curve, ...samples(curve) })),
    backgroundCurves: pattern.backgroundCurves?.map((curve) => ({
      ...curve,
      ...samples(curve),
    })),
    phaseLines: pattern.phaseLines?.flatMap((line) => {
      const x = xValue(line.x);
      return x != null && Number.isFinite(x) ? [{ ...line, x }] : [];
    }),
  };
}

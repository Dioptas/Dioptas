import type { Pattern } from "./types";
import type { PlotRange } from "./usePlotNavigation";

/** Qt PhaseModel scaling, evaluated in the plot's displayed intensity scale. */
export function scalePhaseLines(
  pattern: Pattern,
  lines: NonNullable<Pattern["phaseLines"]>,
  view: PlotRange,
  transform: (intensity: number) => number,
): number[] {
  if (!lines.length) return [];
  let maximum = -Infinity;
  for (let i = 0; i < pattern.x.length; i++) {
    const x = pattern.x[i],
      y = pattern.y[i];
    if (x > view.xMin && x < view.xMax && y != null && Number.isFinite(y)) {
      const value = transform(y);
      if (Number.isFinite(value)) maximum = Math.max(maximum, value);
    }
  }
  const height = Math.max(0, Math.min(maximum, view.yMax) - view.yMin);
  const phaseKey = (line: (typeof lines)[number]) =>
    line.phaseIndex ?? JSON.stringify([line.name, line.color]);
  const maxima = new Map<number | string, number>();
  for (const line of lines) {
    if (
      line.x > view.xMin &&
      line.x < view.xMax &&
      Number.isFinite(line.intensity)
    ) {
      const key = phaseKey(line);
      maxima.set(key, Math.max(maxima.get(key) ?? 0, line.intensity));
    }
  }
  return lines.map((line) => {
    const maximum = maxima.get(phaseKey(line)) ?? 0;
    return (
      view.yMin +
      (maximum > 0 && Number.isFinite(line.intensity)
        ? (height * Math.max(0, line.intensity)) / maximum
        : 0)
    );
  });
}

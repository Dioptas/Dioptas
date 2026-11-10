import { visibleSamples } from "./patternSamples.ts";
import type { Pattern } from "./types";
import type { PlotRange } from "./usePlotNavigation";

type PhaseReference = NonNullable<Pattern["phaseLines"]>[number];

/** Shared relative reflection strengths: each visible phase has its own maximum. */
export function scalePhaseReflections(
  lines: readonly PhaseReference[],
  height: number,
  visible: (line: PhaseReference) => boolean = () => true,
): number[] {
  const phaseKey = (line: PhaseReference) =>
    line.phaseIndex ?? JSON.stringify([line.name, line.color]);
  const maxima = new Map<number | string, number>();
  for (const line of lines) {
    if (visible(line) && Number.isFinite(line.intensity)) {
      const key = phaseKey(line);
      maxima.set(key, Math.max(maxima.get(key) ?? 0, line.intensity));
    }
  }
  return lines.map((line) => {
    const maximum = maxima.get(phaseKey(line)) ?? 0;
    return maximum > 0 && Number.isFinite(line.intensity)
      ? (height * Math.max(0, line.intensity)) / maximum
      : 0;
  });
}

/** Qt PhaseModel scaling, evaluated in the plot's displayed intensity scale. */
export function scalePhaseLines(
  pattern: Pick<Pattern, "x" | "y">,
  lines: NonNullable<Pattern["phaseLines"]>,
  view: PlotRange,
  transform: (intensity: number) => number,
): number[] {
  if (!lines.length) return [];
  let maximum = -Infinity;
  const [start, end] = visibleSamples(pattern.x, view.xMin, view.xMax, false);
  for (let i = start; i < end; i++) {
    const x = pattern.x[i],
      y = pattern.y[i];
    if (x > view.xMin && x < view.xMax && y != null && Number.isFinite(y)) {
      const value = transform(y);
      if (Number.isFinite(value)) maximum = Math.max(maximum, value);
    }
  }
  const height = Math.max(0, Math.min(maximum, view.yMax) - view.yMin);
  return scalePhaseReflections(
    lines,
    height,
    (line) => line.x > view.xMin && line.x < view.xMax,
  ).map((height) => view.yMin + height);
}

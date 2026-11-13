import type { CakeProfile } from "./types";

/** Display-only row wrap of native samples, matching the cake's azimuth slider. */
export function shiftCakeProfile(
  source: CakeProfile,
  degrees: number,
): CakeProfile {
  const rows = source.y.length;
  const step = rows > 1 ? (source.x[rows - 1] - source.x[0]) / (rows - 1) : 0;
  const period = step * rows;
  const shiftBins = period >= 359 ? Math.round((degrees / period) * rows) : 0;
  if (!shiftBins || !rows) return source;
  const offset = ((shiftBins % rows) + rows) % rows;
  return {
    ...source,
    x: source.x.map((value) => value - shiftBins * step),
    y: source.y.map((_, row) => source.y[(row - offset + rows) % rows]),
    shiftBins,
  };
}

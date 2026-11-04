import { useState } from "react";
import type { Raster } from "./types";

/** Reset contrast in the same render as the source, before any canvas paints. */
export function useRasterLevels(raster: Raster | null) {
  const source = raster?.data;
  const [current, setCurrent] = useState({
    source,
    limits: raster?.limits ?? ([0, 1] as [number, number]),
  });
  const limits =
    current.source === source
      ? current.limits
      : (raster?.limits ?? ([0, 1] as [number, number]));
  if (current.source !== source) setCurrent({ source, limits });
  const setLimits = (next: [number, number]) =>
    setCurrent((previous) =>
      previous.source === source ? { source, limits: next } : previous,
    );
  return [limits, setLimits] as const;
}

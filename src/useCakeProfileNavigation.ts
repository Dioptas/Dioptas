import { useState } from "react";
import {
  detectorViewport,
  type ViewportMemory,
  type PlotViewport,
} from "./plotViewport";
import type { PlotRange } from "./usePlotNavigation";
import type { Cake } from "./types";

/** One source-pixel viewport for the cake and its row-aligned projection. */
export function useCakeProfileNavigation(
  memory: ViewportMemory,
  key: string,
  cake: Cake | null,
) {
  const [, render] = useState(0);
  const stored = detectorViewport(memory, key);
  const fit: PlotRange = {
    xMin: 0,
    xMax: cake?.fullWidth ?? 1,
    yMin: 0,
    yMax: cake?.fullHeight ?? 1,
  };
  const viewport: PlotViewport = {
    key,
    read: stored.read,
    write: (range) => {
      stored.write(range);
      render((v) => v + 1);
    },
  };
  return {
    viewport,
    cakeView: stored.read() ?? fit,
    onAzimuthRange: (range: [number, number]) => {
      const previous = stored.read() ?? fit;
      viewport.write({ ...previous, yMin: range[0], yMax: range[1] });
    },
  };
}

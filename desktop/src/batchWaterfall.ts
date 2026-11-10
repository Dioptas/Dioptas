import { useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import {
  isPlotSecondaryGesture,
  type PlotBounds,
  type ScreenPoint,
  type ZoomSelection,
} from "./usePlotNavigation";

/** Coordinates remain in stored bin/row space even on descending d axes. Rust
 * truncates and clips the endpoints, then takes half-open slices like Qt. */
export interface BatchWaterfallRegion {
  bins: [number, number];
  rows: [number, number];
}
export interface BatchWaterfallSelection {
  active: boolean;
  region: BatchWaterfallRegion | null;
  select: (region: BatchWaterfallRegion) => void;
  cancel: () => void;
}

/** Intercept only unmodified primary drags. All other plot navigation keeps its owner. */
export function useBatchWaterfallDrag(
  mode: BatchWaterfallSelection | undefined,
  ready: boolean,
  bounds: PlotBounds,
  screen: (e: PointerEvent<HTMLCanvasElement>) => ScreenPoint,
  data: (p: ScreenPoint) => ScreenPoint,
) {
  const drag = useRef<{
    start: ScreenPoint;
    canvas: HTMLCanvasElement;
    id: number;
  } | null>(null);
  const [selection, setSelection] = useState<ZoomSelection | null>(null);
  const clamp = (p: ScreenPoint): ScreenPoint => ({
    x: Math.max(bounds.left, Math.min(bounds.left + bounds.width, p.x)),
    y: Math.max(bounds.top, Math.min(bounds.top + bounds.height, p.y)),
  });
  const cancel = () => {
    const d = drag.current;
    drag.current = null;
    setSelection(null);
    if (d?.canvas.hasPointerCapture(d.id)) d.canvas.releasePointerCapture(d.id);
  };
  useEffect(() => {
    if (!mode?.active || !ready) cancel();
  }, [mode?.active, ready]);
  return {
    selection,
    drawing: () => drag.current !== null,
    cancel,
    down: (e: PointerEvent<HTMLCanvasElement>) => {
      if (drag.current) return true;
      if (!mode?.active || e.button !== 0 || isPlotSecondaryGesture(e))
        return false;
      if (!ready) return true;
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);
      drag.current = {
        start: clamp(screen(e)),
        canvas: e.currentTarget,
        id: e.pointerId,
      };
      return true;
    },
    move: (e: PointerEvent<HTMLCanvasElement>) => {
      if (!drag.current) return false;
      if (e.pointerId !== drag.current.id) return true;
      setSelection({ start: drag.current.start, end: clamp(screen(e)) });
      return true;
    },
    up: (e: PointerEvent<HTMLCanvasElement>) => {
      const d = drag.current;
      if (!d) return false;
      if (e.pointerId !== d.id) return true;
      const end = clamp(screen(e));
      cancel();
      if (
        Math.abs(end.x - d.start.x) >= 4 &&
        Math.abs(end.y - d.start.y) >= 4
      ) {
        const a = data(d.start),
          b = data(end);
        mode?.select({ bins: [a.x, b.x], rows: [a.y, b.y] });
      }
      return true;
    },
  };
}

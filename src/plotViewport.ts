import type { PlotRange } from "./usePlotNavigation";
import type { State, Unit } from "./types";
import { radialValues } from "./radialReadout.ts";

type Scale = "linear" | "log" | "sqrt";
export interface PlotViewport {
  key: string;
  read: () => PlotRange | null;
  write: (range: PlotRange | null) => void;
}
interface SavedViewport {
  context: string;
  range: PlotRange | null;
  unit?: Unit;
  scale?: Scale;
}
export type ViewportMemory = { current: SavedViewport | null };
export interface SharedPlotViews {
  detector: ViewportMemory;
  pattern: ViewportMemory;
}
export function createPlotViews(): SharedPlotViews {
  return { detector: { current: null }, pattern: { current: null } };
}
export function plotViewContext(state: State | null) {
  return JSON.stringify([
    state?.configurationContext ?? state?.configurationIndex,
    state?.shape,
    state?.calibration.transformations,
  ]);
}
export function detectorViewport(
  memory: ViewportMemory,
  context: string,
): PlotViewport {
  return {
    key: context,
    read: () =>
      memory.current?.context === context ? memory.current.range : null,
    write: (range) => {
      memory.current = { context, range };
    },
  };
}
const scaleY = (y: number, scale: Scale) =>
  scale === "log"
    ? Math.log10(Math.max(1e-6, y))
    : scale === "sqrt"
      ? Math.sqrt(Math.max(0, y))
      : y;
const unscaleY = (y: number, scale: Scale) =>
  scale === "log" ? 10 ** y : scale === "sqrt" ? y * Math.abs(y) : y;

/** Store pattern ranges in their source unit/scale; adapt to the destination plot. */
export function patternViewport(
  memory: ViewportMemory,
  context: string,
  unit: Unit,
  scale: Scale,
  wavelength?: number,
): PlotViewport {
  context = JSON.stringify([context, wavelength]);
  return {
    key: JSON.stringify([context, unit, scale]),
    read: () => {
      const saved = memory.current;
      if (saved?.context !== context || !saved.range) return null;
      const range = saved.range;
      const x = [range.xMin, range.xMax].map((v) =>
        saved.unit === unit
          ? v
          : radialValues(v, saved.unit!, wavelength)[unit],
      );
      const y = [range.yMin, range.yMax].map((v) =>
        saved.scale === scale ? v : scaleY(unscaleY(v, saved.scale!), scale),
      );
      if (
        !x.every((v): v is number => v != null && Number.isFinite(v)) ||
        !y.every(Number.isFinite)
      )
        return null;
      const converted = {
        xMin: Math.min(...x),
        xMax: Math.max(...x),
        yMin: Math.min(...y),
        yMax: Math.max(...y),
      };
      return converted.xMin < converted.xMax && converted.yMin < converted.yMax
        ? converted
        : null;
    },
    write: (range) => {
      memory.current = { context, range, unit, scale };
    },
  };
}

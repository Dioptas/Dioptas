import { useCallback, useEffect, useRef, useState } from "react";
import type { PlotUnit, Unit } from "./types";

export type PlotSource =
  "detector" | "cake" | "pattern" | "map" | "batch" | "profile";
export type PlotField = {
  label: string;
  value: string;
  title?: string;
  unit?: Unit;
  kind?: "radial" | "pixel" | "coordinate" | "intensity";
};
export type PlotReading = {
  text: string;
  fields?: PlotField[];
  x?: number;
  row?: number;
  value?: number | null;
  hint?: string;
};
export type ReportPlot = (
  source: PlotSource,
  reading: PlotReading | null,
) => void;
export type PatternHover<U extends PlotUnit = Unit> = {
  x: number;
  y: number | null;
  mouseY: number;
  xResolution?: number;
  yResolution?: number;
  unit: U;
  hint?: string;
};

/** One trailing throttle for the active plot; leaving clears it immediately. */
export function usePlotReadout() {
  const [reading, setReading] = useState<
    (PlotReading & { source: PlotSource }) | null
  >(null);
  const latest = useRef<typeof reading>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const last = useRef(0);
  const clear = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    latest.current = null;
    setReading(null);
  }, []);
  const report = useCallback<ReportPlot>(
    (source, value) => {
      if (!value) {
        if (latest.current?.source === source) clear();
        return;
      }
      latest.current = { source, ...value };
      if (timer.current) return;
      timer.current = setTimeout(
        () => {
          timer.current = null;
          last.current = performance.now();
          setReading(latest.current);
        },
        Math.max(0, 100 - (performance.now() - last.current)),
      );
    },
    [clear],
  );
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  return { reading, report, clear };
}

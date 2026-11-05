import { radialValues } from "./radialReadout.ts";
import type { Unit } from "./types";
import { useState } from "react";
import type { BatchData } from "./batchDomain";
import type { PlotRange, ZoomMode } from "./usePlotNavigation";
import type { PlotViewport } from "./plotViewport";

interface Display {
  id: string;
  limits: [number, number];
  log: boolean;
  sqrt: boolean;
  palette: string;
  range: PlotRange | null;
  zoomMode: ZoomMode;
  auto: boolean;
  initialized: boolean;
}
const key = "dioptas-batch:display";
function read(batch: BatchData | null): Display {
  const fallback: Display = {
    id: batch?.id ?? "",
    limits: batch?.raster.limits ?? [0, 1],
    log: false,
    sqrt: false,
    palette: "grey",
    range: null,
    zoomMode: "rectangle",
    auto: true,
    initialized: false,
  };
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? "null");
    fallback.zoomMode =
      saved?.zoomMode === "horizontal" ? "horizontal" : "rectangle";
    if (
      saved?.id === batch?.id &&
      saved.limits?.length === 2 &&
      saved.limits.every(Number.isFinite) &&
      saved.limits[0] < saved.limits[1]
    )
      return {
        ...saved,
        zoomMode: fallback.zoomMode,
      };
  } catch {
    /* New series uses its own automatic limits. */
  }
  return fallback;
}
export function useBatchDisplay(batch: BatchData | null) {
  const [display, setDisplay] = useState(() => read(batch));
  const current = display.id === (batch?.id ?? "") ? display : read(batch);
  if (current !== display) setDisplay(current);
  const update = (patch: Partial<Display>) => {
    const next = { ...current, ...patch, initialized: true };
    setDisplay(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      /* Keep the session's display. */
    }
  };
  const viewport: PlotViewport = {
    key: current.id,
    read: () => current.range,
    write: (range) => update({ range }),
  };
  return { ...current, update, viewport };
}

/** Convert labels only; retain every matrix column and its recorded wavelength. */
export function batchDisplayInUnit(batch: BatchData, unit: Unit): BatchData {
  if (batch.unit === unit) return batch;
  const x = batch.x.map(
    (value) =>
      radialValues(value, batch.unit, batch.wavelength ?? undefined)[unit],
  );
  if (x.some((value) => value == null || !Number.isFinite(value))) return batch;
  return { ...batch, x: x as number[], unit };
}

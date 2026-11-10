import type { PlotRange } from "./usePlotNavigation";
import type { BatchData } from "./batchDomain";

/** Raster IDs change on normalization/background subtraction. Camera identity
 * follows the acquired series instead, across those display products and units.
 */
export function batchSurfaceSeriesKey(batch: BatchData) {
  const source = JSON.stringify([
    batch.files,
    batch.entries.length,
    batch.entries[0],
    batch.entries.at(-1),
    batch.sourceUnit,
  ]);
  let hash = 2166136261;
  for (let i = 0; i < source.length; i++)
    hash = Math.imul(hash ^ source.charCodeAt(i), 16777619);
  return (hash >>> 0).toString(16);
}

// Qt raises frame stride above 500,000 values. Resolution presets additionally
// bound the display mesh: these are source samples, never scientific changes.
export const QT_SURFACE_SIZE = 500_000;
export const SURFACE_VERTEX_LIMIT = 8_192;
export const SURFACE_COLUMN_LIMIT = 256;
export const surfaceResolutions = {
  fast: {
    label: "Fast",
    vertices: SURFACE_VERTEX_LIMIT,
    columns: SURFACE_COLUMN_LIMIT,
  },
  high: { label: "High", vertices: 65_536, columns: 2_048 },
  fine: { label: "Very high", vertices: 262_144, columns: 8_192 },
} as const;
export type SurfaceResolution = keyof typeof surfaceResolutions;
export type SurfaceScale = "linear" | "log" | "sqrt";
export type SurfaceOrientation = "Front" | "Right" | "Top" | "Isometric";
export interface SurfaceCamera {
  azimuth: number;
  elevation: number;
  zoom: number;
  panX: number;
  panY: number;
}
export function surfaceCamera(
  view: SurfaceOrientation = "Isometric",
): SurfaceCamera {
  return {
    azimuth: view === "Right" ? 90 : view === "Isometric" ? 45 : 0,
    elevation: view === "Top" ? 90 : view === "Isometric" ? 30 : 0,
    zoom: 1,
    panX: 0,
    panY: 0,
  };
}
export const clamp = (n: number, low: number, high: number) =>
  Math.max(low, Math.min(high, n));

export function surfaceSampling(
  rows: number,
  columns: number,
  range: PlotRange | null,
  requestedStep = 1,
  resolution: SurfaceResolution = "high",
) {
  const budget = surfaceResolutions[resolution];
  const firstRow = clamp(
    Math.floor(range?.yMin ?? 0),
    0,
    Math.max(0, rows - 1),
  );
  const lastRow = clamp(
    Math.ceil(range?.yMax ?? rows) - 1,
    firstRow,
    Math.max(firstRow, rows - 1),
  );
  const firstColumn = clamp(
    Math.floor(range?.xMin ?? 0),
    0,
    Math.max(0, columns - 1),
  );
  const lastColumn = clamp(
    Math.ceil(range?.xMax ?? columns) - 1,
    firstColumn,
    Math.max(firstColumn, columns - 1),
  );
  const columnStep = Math.max(
    1,
    Math.ceil((lastColumn - firstColumn) / (budget.columns - 1)),
  );
  const cols: number[] = [];
  if (columns > 0) {
    for (let c = firstColumn; c <= lastColumn; c += columnStep) cols.push(c);
    if (cols.at(-1) !== lastColumn) cols.push(lastColumn);
  }
  const rowCount = lastRow - firstRow + 1;
  const qtStep = Math.max(
    1,
    Math.floor((rowCount * columns) / QT_SURFACE_SIZE),
  );
  const frameStep = Math.max(
    1,
    Math.floor(requestedStep) || 1,
    qtStep,
    Math.ceil(
      rowCount /
        Math.max(1, Math.floor(budget.vertices / Math.max(1, cols.length))),
    ),
  );
  const frames: number[] = [];
  if (rows > 0)
    for (let r = firstRow; r <= lastRow; r += frameStep) frames.push(r);
  return {
    frames,
    columns: cols,
    frameStep,
    columnStep,
    firstRow,
    lastRow,
    firstColumn,
    lastColumn,
  };
}

/** Exact transfer used by the 2D Canvas raster (log1p from the lower limit).
 * Nonfinite samples form holes. Negative sqrt samples clamp to zero in both views.
 */
export function surfaceIntensity(
  value: number,
  limits: [number, number],
  scale: SurfaceScale,
) {
  if (!Number.isFinite(value)) return NaN;
  if (scale === "sqrt") {
    const lo = Math.sqrt(Math.max(0, limits[0]));
    return clamp(
      (Math.sqrt(Math.max(0, value)) - lo) /
        Math.max(1e-12, Math.sqrt(Math.max(0, limits[1])) - lo),
      0,
      1,
    );
  }
  const span = Math.max(1e-12, limits[1] - limits[0]);
  return clamp(
    scale === "log"
      ? Math.log1p(Math.max(0, value - limits[0])) / Math.log1p(span)
      : (value - limits[0]) / span,
    0,
    1,
  );
}

export interface SurfacePoint {
  x: number;
  y: number;
  depth: number;
}
/** Orthographic projection avoids perspective distortion of the physical axes.
 * Qt uses frame/radial/intensity as x/y/z; retain those camera orientations.
 */
export function surfaceProject(
  frame: number,
  radial: number,
  z: number,
  camera: SurfaceCamera,
  width: number,
  height: number,
  stretch: [number, number, number] = [1, 1, 1],
): SurfacePoint {
  const a = (camera.azimuth * Math.PI) / 180,
    e = (camera.elevation * Math.PI) / 180;
  const x = (frame - 0.5) * 2 * stretch[0],
    y = (radial - 0.5) * 2 * stretch[1];
  const vertical = (z - 0.5) * stretch[2];
  const across = -Math.sin(a) * x + Math.cos(a) * y;
  const away = Math.cos(a) * x + Math.sin(a) * y;
  const up = Math.cos(e) * vertical - Math.sin(e) * away;
  const unit = Math.max(1, Math.min(width / 3.7, height / 3.2)) * camera.zoom;
  return {
    x: width / 2 + across * unit + camera.panX,
    y: height / 2 - up * unit + camera.panY,
    depth: Math.cos(e) * away + Math.sin(e) * vertical,
  };
}

export function surfaceBarycentric(
  x: number,
  y: number,
  a: SurfacePoint,
  b: SurfacePoint,
  c: SurfacePoint,
) {
  const d = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y);
  if (Math.abs(d) < 1e-8) return null;
  const u = ((b.y - c.y) * (x - c.x) + (c.x - b.x) * (y - c.y)) / d;
  const v = ((c.y - a.y) * (x - c.x) + (a.x - c.x) * (y - c.y)) / d;
  return u >= 0 && v >= 0 && u + v <= 1 ? [u, v, 1 - u - v] : null;
}

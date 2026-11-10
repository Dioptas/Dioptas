import { surfaceAxisTicks } from "./batchSurfaceAxes.ts";
import { radialValues } from "./radialReadout.ts";
import type { BatchData } from "./batchDomain";
import type { SurfacePoint, SurfaceScale } from "./batchSurfaceGeometry";
import type { SurfaceTriangle, SurfaceVertex } from "./batchSurfaceRenderer";

export type SurfacePhaseStyle = "lines" | "planes";
export interface SurfaceGuideSegment {
  points: [SurfacePoint, SurfacePoint];
  color: string;
  width: number;
}
export interface SurfaceGuidePlane {
  points: [SurfacePoint, SurfacePoint, SurfacePoint, SurfacePoint];
  color: string;
  opacity: number;
}
export interface SurfaceGuides {
  contours: number[];
  segments: SurfaceGuideSegment[];
  planes: SurfaceGuidePlane[];
}

/** Rounded physical intensity levels, transformed by the very same mapping as
 * the surface/axes. Omit the clipped floor and ceiling, which are flat regions. */
export function surfaceContourLevels(
  limits: [number, number],
  scale: SurfaceScale,
) {
  if (!limits.every(Number.isFinite) || limits[1] <= limits[0]) return [];
  return surfaceAxisTicks(...limits, 8, scale)
    .ticks.filter((t) => t.fraction > 1e-6 && t.fraction < 1 - 1e-6)
    .slice(0, 12);
}

/** Slice the rendered triangle, rather than a separate interpolated matrix.
 * This keeps a reference curve on the actual mesh at every sampling resolution,
 * including descending radial coordinates, clipped values and missing-data holes. */
export function sliceSurfaceTriangle(
  triangle: SurfaceTriangle,
  field: "radial" | "z",
  value: number,
): [SurfaceVertex, SurfaceVertex] | null {
  if (
    !Number.isFinite(value) ||
    triangle.some((p) => !Number.isFinite(p[field]))
  )
    return null;
  const points: SurfaceVertex[] = [];
  const add = (p: SurfaceVertex) => {
    if (
      !points.some(
        (q) => Math.hypot(p.x - q.x, p.y - q.y, p.depth - q.depth) < 1e-8,
      )
    )
      points.push(p);
  };
  if (triangle.every((p) => p[field] === value)) return null;
  for (let i = 0; i < 3; i++) {
    const a = triangle[i],
      b = triangle[(i + 1) % 3];
    if (a[field] === value) add(a);
    if (
      (a[field] < value && b[field] > value) ||
      (b[field] < value && a[field] > value)
    ) {
      const t = (value - a[field]) / (b[field] - a[field]);
      const blend = (key: Exclude<keyof SurfaceVertex, "meshIndex">) =>
        a[key] + t * (b[key] - a[key]);
      add({
        x: blend("x"),
        y: blend("y"),
        depth: blend("depth"),
        frame: blend("frame"),
        radial: blend("radial"),
        intensity: blend("intensity"),
        z: blend("z"),
        meshIndex: -1,
      });
    }
  }
  return points.length === 2 ? [points[0], points[1]] : null;
}

/** Use the native phase model's d spacings and the acquired batch wavelength,
 * independent of whatever radial unit the current pattern happens to display. */
export function surfacePhaseReferences(
  batch: Pick<BatchData, "unit" | "wavelength">,
  lines: BatchData["phaseLines"],
  radialEdges: [number, number],
) {
  const lo = Math.min(...radialEdges),
    hi = Math.max(...radialEdges);
  return (lines ?? []).flatMap((line) => {
    if (!(line.x > 0) || !Number.isFinite(line.x)) return [];
    const radial = radialValues(line.x, "d_A", batch.wavelength ?? undefined)[
      batch.unit
    ];
    return radial != null &&
      Number.isFinite(radial) &&
      radial >= lo &&
      radial <= hi
      ? [{ ...line, radial }]
      : [];
  });
}

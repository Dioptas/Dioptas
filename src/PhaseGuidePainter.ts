import type { RingOverlay } from "./types";
import { forEachPoint, pointStorage, samePoints } from "./phaseGuidePoints";

export interface PhaseProjection {
  width: number;
  height: number;
  dpr: number;
  left: number;
  top: number;
  plotWidth: number;
  plotHeight: number;
  sx: number;
  sy: number;
  ox: number;
  oy: number;
  fullHeight: number;
}
type CachedPath = { projection: number[]; path: Path2D };
const equal = (a: number[], b: number[]) =>
  a.length === b.length && a.every((v, i) => v === b[i]);
const sameRings = (a: RingOverlay[], b: RingOverlay[]) =>
  a.length === b.length &&
  a.every((r, i) => {
    const old = b[i];
    return (
      r.color === old.color &&
      r.lineWidth === old.lineWidth &&
      r.opacity === old.opacity &&
      samePoints(r.points, old.points)
    );
  });

/** Retain native paths and one transparent phase layer. Detector pixels, click
 * guides, calibration picking and exports keep their existing drawing order. */
export class PhaseGuidePainter {
  private paths = new WeakMap<object, Map<string, CachedPath>>();
  private layer: HTMLCanvasElement | null = null;
  private groups: { canvas: HTMLCanvasElement; rings: RingOverlay[] }[] = [];
  private previous: { projection: number[]; rings: RingOverlay[] } | null =
    null;
  private path(ring: RingOverlay, p: PhaseProjection) {
    const points = ring.points;
    const source = pointStorage(points);
    let paths = this.paths.get(source);
    if (!paths) this.paths.set(source, (paths = new Map()));
    const key = Array.isArray(points)
      ? "all"
      : `${points.offset}:${points.length}`;
    const projection = [p.sx, p.sy, p.ox, p.oy, p.fullHeight];
    const hit = paths.get(key);
    if (hit && equal(hit.projection, projection)) return hit.path;
    const path = new Path2D();
    forEachPoint(points, (x, y, i) => {
      const px = p.ox + x * p.sx,
        py = p.oy + (p.fullHeight - y) * p.sy;
      if (i) path.lineTo(px, py);
      else path.moveTo(px, py);
    });
    paths.set(key, { projection, path });
    return path;
  }
  private paint(
    layer: HTMLCanvasElement,
    rings: RingOverlay[],
    p: PhaseProjection,
  ) {
    layer.dataset.testid = "phase-lines-layer";
    const width = Math.max(1, Math.round(p.width * p.dpr)),
      height = Math.max(1, Math.round(p.height * p.dpr));
    if (layer.width !== width) layer.width = width;
    if (layer.height !== height) layer.height = height;
    const ctx = layer.getContext("2d")!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.scale(p.dpr, p.dpr);
    ctx.beginPath();
    ctx.rect(p.left, p.top, p.plotWidth, p.plotHeight);
    ctx.clip();
    ctx.setLineDash([]);
    for (const ring of rings) {
      ctx.strokeStyle = ring.color ?? "#ff4040b3";
      ctx.lineWidth = ring.lineWidth ?? 0.8;
      ctx.globalAlpha = ring.opacity ?? 1;
      ctx.stroke(this.path(ring, p));
    }
    ctx.restore();
  }
  draw(
    context: CanvasRenderingContext2D,
    rings: RingOverlay[],
    p: PhaseProjection,
    exporting = false,
  ) {
    // Export the native vector paths directly at the requested resolution;
    // raster cache compositing is solely an interactive-display optimization.
    if (exporting) {
      context.save();
      context.setLineDash([]);
      for (const ring of rings) {
        context.strokeStyle = ring.color ?? "#ff4040b3";
        context.lineWidth = ring.lineWidth ?? 0.8;
        context.globalAlpha = ring.opacity ?? 1;
        context.stroke(this.path(ring, p));
      }
      context.restore();
      return;
    }
    const projection = [
      p.width,
      p.height,
      p.dpr,
      p.left,
      p.top,
      p.plotWidth,
      p.plotHeight,
      p.sx,
      p.sy,
      p.ox,
      p.oy,
      p.fullHeight,
    ];
    const previous = this.previous;
    const same =
      previous &&
      equal(previous.projection, projection) &&
      sameRings(rings, previous.rings);
    if (!same) {
      const layer =
        this.layer ?? (this.layer = document.createElement("canvas"));
      const width = Math.max(1, Math.round(p.width * p.dpr)),
        height = Math.max(1, Math.round(p.height * p.dpr));
      // Add up to eight group surfaces only when all backing stores fit
      // 64 MiB. Larger views retain just the single combined layer.
      const slots = Math.min(
        8,
        Math.floor((64 * 1024 * 1024) / (width * height * 4)) - 1,
      );
      const sameView = previous && equal(previous.projection, projection);
      const priorSources = new Set(
        previous?.rings.map((r) => pointStorage(r.points)),
      );
      const allMoved =
        sameView &&
        rings.length > 0 &&
        !rings.some((r) => priorSources.has(pointStorage(r.points)));
      const phases: RingOverlay[][] = [];
      for (const ring of rings) {
        const last = phases.at(-1);
        if (last && last[0].phaseIndex === ring.phaseIndex) last.push(ring);
        else phases.push([ring]);
      }
      // When every phase moves, no group bitmap can be reused. Paint the
      // combined layer once instead of rebuilding and copying every group.
      if (slots >= 2 && phases.length > 1 && !allMoved) {
        const stride = Math.ceil(phases.length / slots);
        const next: typeof this.groups = [];
        for (let start = 0; start < phases.length; start += stride) {
          const part = phases.slice(start, start + stride).flat();
          const old = this.groups[next.length];
          const canvas = old?.canvas ?? document.createElement("canvas");
          if (!sameView || !old || !sameRings(part, old.rings))
            this.paint(canvas, part, p);
          next.push({ canvas, rings: part });
        }
        this.groups = next;
        if (layer.width !== width) layer.width = width;
        if (layer.height !== height) layer.height = height;
        const ctx = layer.getContext("2d")!;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, width, height);
        for (const group of next) ctx.drawImage(group.canvas, 0, 0);
      } else {
        this.groups = [];
        this.paint(layer, rings, p);
      }
      this.previous = { projection, rings };
    }
    context.save();
    context.globalAlpha = 1;
    context.imageSmoothingEnabled = false;
    // Copy at matching device pixels, including fractional CSS canvas sizes.
    context.drawImage(
      this.layer!,
      0,
      0,
      this.layer!.width / p.dpr,
      this.layer!.height / p.dpr,
    );
    context.restore();
  }
}

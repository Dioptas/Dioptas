import { rasterColor } from "./colorMaps";
import { batchRadialBin } from "./batchPlot";
import { unitLabel } from "./types";
import type { BatchData } from "./batchDomain";
import { scientificValue } from "./ScientificNumberInput";
import {
  clamp,
  surfaceBarycentric,
  surfaceIntensity,
  surfaceProject,
  type SurfaceCamera,
  type SurfacePoint,
  type SurfaceScale,
  type surfaceSampling,
} from "./batchSurfaceGeometry";

export interface SurfaceVertex extends SurfacePoint {
  frame: number;
  radial: number;
  intensity: number;
  z: number;
}
export type SurfaceTriangle = [SurfaceVertex, SurfaceVertex, SurfaceVertex];
export interface SurfaceScene {
  triangles: SurfaceTriangle[];
  vertices: SurfaceVertex[];
}
export function drawBatchSurface(
  canvas: HTMLCanvasElement,
  opts: {
    batch: BatchData;
    values: Float32Array | Uint8Array;
    sampling: ReturnType<typeof surfaceSampling>;
    size: { width: number; height: number };
    camera: SurfaceCamera;
    stretch: [number, number, number];
    limits: [number, number];
    scale: SurfaceScale;
    palette: string;
    marker: number | null;
    font: string;
    muted: string;
  },
): SurfaceScene | null {
  const {
    batch,
    values,
    sampling: s,
    size,
    camera,
    stretch,
    limits,
    scale,
  } = opts;
  // Bound the backing store on high-DPI monitors and unusually large windows.
  const dpr = Math.min(
    window.devicePixelRatio || 1,
    2,
    2048 / Math.max(1, size.width, size.height),
  );
  canvas.width = Math.max(1, Math.round(size.width * dpr));
  canvas.height = Math.max(1, Math.round(size.height * dpr));
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    canvas.dataset.renderState = "unavailable";
    return null;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#17191e";
  ctx.fillRect(0, 0, size.width, size.height);
  const radialFirst = batch.x[s.firstColumn],
    radialLast = batch.x[s.lastColumn];
  const radialSpan = radialLast - radialFirst;
  const project = (frame: number, radial: number, z: number) =>
    surfaceProject(
      s.firstRow === s.lastRow
        ? 0.5
        : (frame - s.firstRow) / (s.lastRow - s.firstRow),
      radialSpan === 0 ? 0.5 : (radial - radialFirst) / radialSpan,
      z,
      camera,
      size.width,
      size.height,
      stretch,
    );
  const vertex = (frame: number, column: number): SurfaceVertex => {
    const intensity = values[frame * batch.x.length + column];
    const z = surfaceIntensity(intensity, limits, scale);
    const radial = batch.x[column];
    return { ...project(frame, radial, z), frame, radial, intensity, z };
  };
  const vertices = s.frames.flatMap((frame) =>
    s.columns.map((column) => vertex(frame, column)),
  );
  const triangles: SurfaceTriangle[] = [];
  const nc = s.columns.length;
  for (let r = 0; r < s.frames.length - 1; r++)
    for (let c = 0; c < nc - 1; c++) {
      const a = vertices[r * nc + c],
        b = vertices[(r + 1) * nc + c];
      const d = vertices[r * nc + c + 1],
        e = vertices[(r + 1) * nc + c + 1];
      for (const tri of [
        [a, b, d],
        [b, e, d],
      ] as SurfaceTriangle[]) {
        if (tri.every((p) => Number.isFinite(p.z) && Number.isFinite(p.radial)))
          triangles.push(tri);
      }
    }
  // Painter's order also defines hit testing: frontmost triangle wins.
  triangles.sort(
    (a, b) =>
      a.reduce((sum, p) => sum + p.depth, 0) -
      b.reduce((sum, p) => sum + p.depth, 0),
  );
  const line = (points: SurfacePoint[], color: string, width = 1) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    let connected = false;
    for (const p of points) {
      if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) {
        connected = false;
        continue;
      }
      if (connected) ctx.lineTo(p.x, p.y);
      else ctx.moveTo(p.x, p.y);
      connected = true;
    }
    ctx.stroke();
  };
  for (let t = 0; t <= 1; t += 0.25) {
    line(
      [
        surfaceProject(t, 0, 0, camera, size.width, size.height, stretch),
        surfaceProject(t, 1, 0, camera, size.width, size.height, stretch),
      ],
      "#343a43",
    );
    line(
      [
        surfaceProject(0, t, 0, camera, size.width, size.height, stretch),
        surfaceProject(1, t, 0, camera, size.width, size.height, stretch),
      ],
      "#343a43",
    );
  }
  const colors = Array.from(
    { length: 256 },
    (_, i) => `rgb(${rasterColor(i / 255, opts.palette).join(",")})`,
  );
  for (const tri of triangles) {
    ctx.fillStyle =
      colors[Math.round((tri.reduce((sum, p) => sum + p.z, 0) / 3) * 255)];
    ctx.beginPath();
    ctx.moveTo(tri[0].x, tri[0].y);
    ctx.lineTo(tri[1].x, tri[1].y);
    ctx.lineTo(tri[2].x, tri[2].y);
    ctx.closePath();
    ctx.fill();
  }
  // A one-frame or one-bin batch remains inspectable as a curve/point.
  if (!triangles.length) {
    line(vertices, colors[160], 2);
    for (const p of vertices)
      if (Number.isFinite(p.z)) {
        ctx.fillStyle = colors[Math.round(p.z * 255)];
        ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
      }
  }
  if (batch.selected >= s.firstRow && batch.selected <= s.lastRow)
    line(
      s.columns.map((c) => vertex(batch.selected, c)),
      "#ff9500",
      2,
    );
  const markerBin =
    opts.marker == null ? null : batchRadialBin(opts.marker, batch.x);
  if (markerBin != null) {
    const column = clamp(Math.round(markerBin - 0.5), 0, batch.x.length - 1);
    if (column >= s.firstColumn && column <= s.lastColumn)
      line(
        s.frames.map((r) => vertex(r, column)),
        "#63e09a",
        2,
      );
  }
  ctx.font = opts.font;
  ctx.fillStyle = opts.muted;
  ctx.textAlign = "center";
  const text = (label: string, p: SurfacePoint, offset = 0) =>
    ctx.fillText(
      label,
      clamp(
        p.x,
        Math.min(65, size.width / 2),
        Math.max(size.width / 2, size.width - 65),
      ),
      clamp(p.y + offset, 14, Math.max(14, size.height - 6)),
    );
  const origin = surfaceProject(
    0,
    0,
    0,
    camera,
    size.width,
    size.height,
    stretch,
  );
  const frameEnd = surfaceProject(
    1,
    0,
    0,
    camera,
    size.width,
    size.height,
    stretch,
  );
  const radialEnd = surfaceProject(
    0,
    1,
    0,
    camera,
    size.width,
    size.height,
    stretch,
  );
  const zEnd = surfaceProject(
    0,
    0,
    1,
    camera,
    size.width,
    size.height,
    stretch,
  );
  for (const end of [frameEnd, radialEnd, zEnd])
    line([origin, end], opts.muted);
  // Suppress a collapsed axis in an orthogonal view. The fixed label above
  // still identifies the scale and clipping limits, including top orientation.
  if (Math.hypot(frameEnd.x - origin.x, frameEnd.y - origin.y) > 30) {
    text(String(s.firstRow + 1), origin, 16);
    text(String(s.lastRow + 1), frameEnd, 16);
    text(
      "Frame",
      surfaceProject(0.5, 0, 0, camera, size.width, size.height, stretch),
      32,
    );
  }
  if (Math.hypot(radialEnd.x - origin.x, radialEnd.y - origin.y) > 30) {
    text(scientificValue(radialFirst), origin, -8);
    text(scientificValue(radialLast), radialEnd, -8);
    text(
      unitLabel(batch.unit),
      surfaceProject(0, 0.5, 0, camera, size.width, size.height, stretch),
      -24,
    );
  }
  if (Math.hypot(zEnd.x - origin.x, zEnd.y - origin.y) > 30)
    text(scientificValue(limits[1]), zEnd, -8);
  ctx.textAlign = "left";
  ctx.fillText(
    `I · ${scale === "log" ? "log" : scale === "sqrt" ? "√" : "linear"} · ${scientificValue(limits[0])}–${scientificValue(limits[1])}`,
    8,
    18,
  );
  const finite = vertices.some((p) => Number.isFinite(p.z));
  canvas.dataset.renderState = finite ? "ready" : "empty";
  if (!finite) {
    ctx.textAlign = "center";
    ctx.fillText(
      "No finite intensities in this range.",
      size.width / 2,
      size.height / 2,
    );
  }
  canvas.dataset.triangles = String(triangles.length);
  const sample = triangles.at(-1);
  canvas.dataset.hitSample = JSON.stringify(
    sample
      ? {
          x: sample.reduce((n, p) => n + p.x, 0) / 3,
          y: sample.reduce((n, p) => n + p.y, 0) / 3,
        }
      : vertices[0],
  );
  return { triangles, vertices };
}

export function hitBatchSurface(
  scene: SurfaceScene | null,
  x: number,
  y: number,
) {
  if (!scene) return null;
  for (let i = scene.triangles.length - 1; i >= 0; i--) {
    const tri = scene.triangles[i],
      weights = surfaceBarycentric(x, y, ...tri);
    if (weights)
      return {
        frame: Math.round(tri.reduce((n, p, j) => n + p.frame * weights[j], 0)),
        radial: tri.reduce((n, p, j) => n + p.radial * weights[j], 0),
      };
  }
  let nearest: SurfaceVertex | null = null,
    distance = 12;
  for (const p of scene.vertices) {
    const d = Math.hypot(x - p.x, y - p.y);
    if (d < distance) {
      nearest = p;
      distance = d;
    }
  }
  return nearest && { frame: nearest.frame, radial: nearest.radial };
}

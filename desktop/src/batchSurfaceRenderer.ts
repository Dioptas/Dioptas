import { rasterColor } from "./colorMaps";
import { batchRadialBin } from "./batchPlot";
import { unitLabel } from "./types";
import type { BatchData } from "./batchDomain";
import { drawSurfaceGPU } from "./WebGLSurface";
import {
  sliceSurfaceTriangle,
  surfaceContourLevels,
  surfacePhaseReferences,
  surfacePhaseFrameHeights,
  type SurfaceGuides,
  type SurfacePhaseStyle,
} from "./batchSurfaceGuides";
import { scalePhaseReflections } from "./phaseLineScaling";
import {
  clamp,
  surfaceBarycentric,
  surfaceIntensity,
  type SurfaceCamera,
  type SurfacePoint,
  type SurfaceScale,
  type surfaceSampling,
} from "./batchSurfaceGeometry";

import {
  surfaceAxisProjection,
  layoutSurfaceAxes,
  drawSurfaceAxes,
  surfaceProjectionMatrix,
} from "./batchSurfaceAxes";

export interface SurfaceVertex extends SurfacePoint {
  meshIndex: number;
  frame: number;
  radial: number;
  intensity: number;
  z: number;
}
export type SurfaceTriangle = [SurfaceVertex, SurfaceVertex, SurfaceVertex];
export interface SurfaceScene {
  /** Normalized mesh coordinates when project is supplied; screen coordinates
   * for software drawing and independent picking callers. */
  triangles: SurfaceTriangle[];
  vertices: SurfaceVertex[];
  depthSorted: boolean;
  project?: (point: SurfaceVertex) => SurfaceVertex;
  projected?: SurfaceScene;
}
interface SurfaceMesh {
  key: unknown[];
  vertices: SurfaceVertex[];
  triangles: SurfaceTriangle[];
  references: ReturnType<typeof surfacePhaseReferences>;
  contourLevels: ReturnType<typeof surfaceContourLevels>;
  guides: SurfaceGuides;
  strengths: number[];
  frameHeights: number[];
  triangleReferences: (
    tri: SurfaceTriangle,
  ) => ReturnType<typeof surfacePhaseReferences>;
  sampledMaximum: number;
}
const meshes = new WeakMap<HTMLCanvasElement, SurfaceMesh>();
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
    contours?: boolean;
    phaseLines?: BatchData["phaseLines"];
    phaseStyle?: SurfacePhaseStyle;
    phaseHeights?: number[];
  },
): SurfaceScene | null {
  const started = performance.now();
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
  const pixelWidth = Math.max(1, Math.round(size.width * dpr));
  const pixelHeight = Math.max(1, Math.round(size.height * dpr));
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    canvas.dataset.renderState = "unavailable";
    return null;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#17191e";
  ctx.fillRect(0, 0, size.width, size.height);
  ctx.font = opts.font;
  const fontSize = parseFloat(opts.font) || 13;
  const projectBox = surfaceAxisProjection(
    camera,
    stretch,
    size.width,
    size.height,
    fontSize,
  );
  const radialFirst = batch.x[s.firstColumn],
    radialLast = batch.x[s.lastColumn];
  const radialSpan = radialLast - radialFirst;
  const project = (frame: number, radial: number, z: number) =>
    projectBox(
      s.firstRow === s.lastRow
        ? 0.5
        : (frame - s.firstRow) / (s.lastRow - s.firstRow),
      radialSpan === 0 ? 0.5 : (radial - radialFirst) / radialSpan,
      z,
    );
  const axes = layoutSurfaceAxes({
    project: projectBox,
    width: size.width,
    height: size.height,
    fontSize,
    measure: (text) => ctx.measureText(text).width,
    frames: [s.firstRow + 1, s.lastRow + 1],
    radial: [radialFirst, radialLast],
    radialTitle: unitLabel(batch.unit),
    limits,
    scale,
  });
  const projectWorld = (frame: number, radial: number, z: number) => ({
    x:
      s.firstRow === s.lastRow
        ? 0.5
        : (frame - s.firstRow) / (s.lastRow - s.firstRow),
    y: radialSpan === 0 ? 0.5 : (radial - radialFirst) / radialSpan,
    depth: z,
  });
  const projectVertex = (p: SurfaceVertex): SurfaceVertex => ({
    ...p,
    ...projectBox(p.x, p.y, p.depth),
  });
  const vertex = (
    frame: number,
    column: number,
    meshIndex = -1,
  ): SurfaceVertex => {
    const intensity = values[frame * batch.x.length + column];
    const z = surfaceIntensity(intensity, limits, scale);
    const radial = batch.x[column];
    return {
      ...projectWorld(frame, radial, z),
      frame,
      radial,
      intensity,
      z,
      meshIndex,
    };
  };
  const key = [
    values,
    s,
    batch.x,
    batch.unit,
    batch.wavelength,
    ...limits,
    scale,
    opts.contours,
    opts.phaseLines,
    opts.phaseStyle,
    opts.phaseHeights,
  ];
  let mesh = meshes.get(canvas);
  const reused =
    !!mesh && key.every((value, index) => value === mesh!.key[index]);
  if (!reused) {
    const vertices = s.frames.flatMap((frame, r) =>
      s.columns.map((column, c) =>
        vertex(frame, column, r * s.columns.length + c),
      ),
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
          if (
            tri.every((p) => Number.isFinite(p.z) && Number.isFinite(p.radial))
          )
            triangles.push(tri);
        }
      }
    const contourLevels =
      opts.contours === false ? [] : surfaceContourLevels(limits, scale);
    const references = surfacePhaseReferences(batch, opts.phaseLines, [
      radialFirst,
      radialLast,
    ]).sort((a, b) => a.radial - b.radial);
    // Only visit reflections crossing a triangle's radial interval, avoiding a
    // complete mesh scan per reflection for dense phase lists/high-detail meshes.
    const triangleReferences = (tri: SurfaceTriangle) => {
      const lo = Math.min(...tri.map((p) => p.radial)),
        hi = Math.max(...tri.map((p) => p.radial));
      let first = 0,
        last = references.length;
      while (first < last) {
        const mid = (first + last) >>> 1;
        if (references[mid].radial < lo) first = mid + 1;
        else last = mid;
      }
      const found = [];
      for (
        let i = first;
        i < references.length && references[i].radial <= hi;
        i++
      )
        found.push(references[i]);
      return found;
    };
    const guides: SurfaceGuides = {
      contours: contourLevels.map((t) => t.fraction),
      segments: [],
      planes: [],
    };
    const strengths = scalePhaseReflections(references, 1);
    const frameHeights =
      opts.phaseStyle === "planes" && references.length
        ? (opts.phaseHeights ??
          surfacePhaseFrameHeights(values, batch.x.length, s, limits, scale))
        : [];
    if (opts.phaseStyle === "planes") {
      for (const [index, reference] of references.entries()) {
        const strength = strengths[index];
        if (strength <= 0) continue;
        const tops = s.frames.map((frame, i) =>
          projectWorld(frame, reference.radial, frameHeights[i] * strength),
        );
        const floor = s.frames.map((frame) =>
          projectWorld(frame, reference.radial, 0),
        );
        for (let i = 0; i < tops.length - 1; i++) {
          if (frameHeights[i] <= 0 && frameHeights[i + 1] <= 0) continue;
          guides.planes.push({
            points: [floor[i], floor[i + 1], tops[i], tops[i + 1]],
            color: reference.color,
            opacity: 0.13,
          });
          guides.segments.push({
            points: [tops[i], tops[i + 1]],
            color: reference.color,
            width: 1,
          });
        }
        if (tops.length)
          for (const points of [
            [floor[0], floor.at(-1)!],
            [floor[0], tops[0]],
            [floor.at(-1)!, tops.at(-1)!],
          ] as [SurfacePoint, SurfacePoint][])
            guides.segments.push({ points, color: reference.color, width: 1 });
      }
    } else if (references.length) {
      for (const tri of triangles)
        for (const reference of triangleReferences(tri)) {
          const points = sliceSurfaceTriangle(tri, "radial", reference.radial);
          if (points)
            guides.segments.push({
              points,
              color: reference.color,
              width: 1.8,
            });
        }
    }
    mesh = {
      key,
      vertices,
      triangles,
      references,
      contourLevels,
      guides,
      strengths,
      frameHeights,
      triangleReferences,
      sampledMaximum: vertices.reduce(
        (maximum, p) =>
          Number.isFinite(p.intensity)
            ? Math.max(maximum, p.intensity)
            : maximum,
        -Infinity,
      ),
    };
    meshes.set(canvas, mesh);
  }
  const {
    vertices,
    triangles,
    references,
    contourLevels,
    guides,
    strengths,
    frameHeights,
    triangleReferences,
  } = mesh!;
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
  for (const grid of axes.grids) line(grid, "#343a43");
  const colors = Array.from(
    { length: 256 },
    (_, i) => `rgb(${rasterColor(i / 255, opts.palette).join(",")})`,
  );
  let fallbackPhaseSegments = 0;
  const gpu = triangles.length
    ? drawSurfaceGPU(
        canvas,
        vertices,
        triangles,
        size.width,
        size.height,
        opts.palette,
        guides,
        surfaceProjectionMatrix(projectBox, size.width, size.height),
      )
    : null;
  let fallbackScene: SurfaceScene | null = null;
  if (gpu) ctx.drawImage(gpu, 0, 0, size.width, size.height);
  else {
    // Canvas is the explicit compatibility fallback for unavailable/lost GPU
    // contexts. Its painter order also permits an early hit-test exit.
    const projectedVertices = vertices.map(projectVertex);
    const projectedTriangles = triangles.map(
      (tri) =>
        tri.map((p) => projectedVertices[p.meshIndex]) as SurfaceTriangle,
    );
    fallbackScene = {
      vertices: projectedVertices,
      triangles: projectedTriangles,
      depthSorted: true,
    };
    projectedTriangles.sort(
      (a, b) =>
        a.reduce((n, p) => n + p.depth, 0) - b.reduce((n, p) => n + p.depth, 0),
    );
    for (const tri of projectedTriangles) {
      ctx.fillStyle =
        colors[Math.round((tri.reduce((sum, p) => sum + p.z, 0) / 3) * 255)];
      ctx.beginPath();
      ctx.moveTo(tri[0].x, tri[0].y);
      ctx.lineTo(tri[1].x, tri[1].y);
      ctx.lineTo(tri[2].x, tri[2].y);
      ctx.closePath();
      ctx.fill();
      // Paint each triangle's annotations before nearer faces. Missing samples
      // remain holes, and fallback contours follow the same physical levels.
      for (const level of contourLevels) {
        const points = sliceSurfaceTriangle(tri, "z", level.fraction);
        if (points) {
          line(points, "rgba(0,0,0,.14)", 1);
        }
      }
      for (const reference of references.length
        ? triangleReferences(tri)
        : []) {
        const points = sliceSurfaceTriangle(tri, "radial", reference.radial);
        if (points) {
          line(points, reference.color, 1.8);
          fallbackPhaseSegments++;
        }
      }
    }
  }
  // A one-frame or one-bin batch remains inspectable as a curve/point.
  if (!triangles.length) {
    line(vertices.map(projectVertex), colors[160], 2);
    for (const p of vertices.map(projectVertex))
      if (Number.isFinite(p.z)) {
        ctx.fillStyle = colors[Math.round(p.z * 255)];
        ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
      }
    // A single frame/bin has no faces to slice: mark its intersections or
    // trace the lone radial column, without bridging missing intensities.
    for (const reference of references) {
      if (s.columns.length === 1) {
        line(vertices.map(projectVertex), reference.color, 1.8);
        fallbackPhaseSegments += Math.max(
          0,
          vertices.filter((p) => Number.isFinite(p.z)).length - 1,
        );
      } else
        for (let i = 0; i < vertices.length - 1; i++) {
          const a = vertices[i],
            b = vertices[i + 1];
          if (
            a.frame !== b.frame ||
            !Number.isFinite(a.z) ||
            !Number.isFinite(b.z) ||
            a.radial === b.radial
          )
            continue;
          const t = (reference.radial - a.radial) / (b.radial - a.radial);
          if (t < 0 || t > 1) continue;
          const p = project(a.frame, reference.radial, a.z + t * (b.z - a.z));
          ctx.fillStyle = reference.color;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 2.5, 0, 2 * Math.PI);
          ctx.fill();
          fallbackPhaseSegments++;
          break;
        }
    }
  }
  if (batch.selected >= s.firstRow && batch.selected <= s.lastRow)
    line(
      s.columns.map((c) => projectVertex(vertex(batch.selected, c))),
      "#ff9500",
      2,
    );
  const markerBin =
    opts.marker == null ? null : batchRadialBin(opts.marker, batch.x);
  if (markerBin != null) {
    const column = clamp(Math.round(markerBin - 0.5), 0, batch.x.length - 1);
    if (column >= s.firstColumn && column <= s.lastColumn)
      line(
        s.frames.map((r) => projectVertex(vertex(r, column))),
        "#63e09a",
        2,
      );
  }
  drawSurfaceAxes(ctx, axes, opts.muted);
  canvas.dataset.axisLayout = JSON.stringify({
    axes: axes.axes,
    labels: axes.labels,
    box: [0, 1].flatMap((f) =>
      [0, 1].flatMap((r) => [0, 1].map((z) => projectBox(f, r, z))),
    ),
  });
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
  canvas.dataset.contourLevels = JSON.stringify(
    contourLevels.map((t) => t.value),
  );
  canvas.dataset.phaseReferences = String(references.length);
  canvas.dataset.phasePlaneHeights = JSON.stringify(
    opts.phaseStyle === "planes"
      ? strengths.map((strength) =>
          frameHeights.reduce(
            (maximum, height) => Math.max(maximum, height * strength),
            0,
          ),
        )
      : [],
  );
  canvas.dataset.phaseSegments = String(
    gpu ? guides.segments.length : fallbackPhaseSegments,
  );
  canvas.dataset.phaseStyle =
    gpu && opts.phaseStyle === "planes" ? "planes" : "lines";
  canvas.dataset.renderer = gpu ? "webgl2" : "canvas";
  canvas.dataset.renderMs = String(performance.now() - started);
  canvas.dataset.sampledMaximum = String(mesh!.sampledMaximum);
  canvas.dataset.geometryReused = String(reused);
  canvas.dataset.meshUploads = gpu?.dataset.meshUploads ?? "0";
  const sample = triangles.at(-1)?.map(projectVertex);
  canvas.dataset.hitSample = JSON.stringify(
    sample
      ? {
          x: sample.reduce((n, p) => n + p.x, 0) / 3,
          y: sample.reduce((n, p) => n + p.y, 0) / 3,
        }
      : vertices[0] && projectVertex(vertices[0]),
  );
  return (
    fallbackScene ?? {
      triangles,
      vertices,
      depthSorted: false,
      project: projectVertex,
    }
  );
}

export function hitBatchSurface(
  scene: SurfaceScene | null,
  x: number,
  y: number,
) {
  if (!scene) return null;
  if (scene.project) {
    if (!scene.projected) {
      const vertices = scene.vertices.map(scene.project);
      scene.projected = {
        vertices,
        triangles: scene.triangles.map(
          (tri) => tri.map((p) => vertices[p.meshIndex]) as SurfaceTriangle,
        ),
        depthSorted: false,
      };
    }
    scene = scene.projected;
  }
  let front: { frame: number; radial: number } | null = null,
    depth = -Infinity;
  for (let i = scene.triangles.length - 1; i >= 0; i--) {
    const tri = scene.triangles[i];
    if (
      x < Math.min(tri[0].x, tri[1].x, tri[2].x) ||
      x > Math.max(tri[0].x, tri[1].x, tri[2].x) ||
      y < Math.min(tri[0].y, tri[1].y, tri[2].y) ||
      y > Math.max(tri[0].y, tri[1].y, tri[2].y)
    )
      continue;
    const weights = surfaceBarycentric(x, y, ...tri);
    if (weights) {
      const hit = {
        frame: Math.round(tri.reduce((n, p, j) => n + p.frame * weights[j], 0)),
        radial: tri.reduce((n, p, j) => n + p.radial * weights[j], 0),
      };
      if (scene.depthSorted) return hit;
      const candidate = tri.reduce((n, p, j) => n + p.depth * weights[j], 0);
      if (candidate > depth) {
        depth = candidate;
        front = hit;
      }
    }
  }
  if (front) return front;
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

import { linearAxisTicks } from "./plotTicks.ts";
import {
  clamp,
  surfaceIntensity,
  surfaceProject,
  type SurfaceCamera,
  type SurfacePoint,
  type SurfaceScale,
} from "./batchSurfaceGeometry.ts";

type AxisKind = "frame" | "radial" | "intensity";
type Vector = [number, number, number];
export type SurfaceProjection = (
  frame: number,
  radial: number,
  intensity: number,
) => SurfacePoint;
export interface SurfaceAxisLabel {
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  angle: number;
  axis: AxisKind | "legend";
  role: "title" | "tick" | "legend";
  value?: number;
  bounds: { left: number; top: number; right: number; bottom: number };
}
export interface SurfaceAxisTick {
  value: number;
  label: string;
  fraction: number;
  point: SurfacePoint;
  end: SurfacePoint;
  visible: boolean;
}
export interface SurfaceAxis {
  kind: AxisKind;
  start: SurfacePoint;
  end: SurfacePoint;
  normal: [number, number];
  title: string;
  ticks: SurfaceAxisTick[];
}
const corners: Vector[] = [0, 1].flatMap((f) =>
  [0, 1].flatMap((r) => [0, 1].map((z) => [f, r, z] as Vector)),
);

/** Reserve actual text margins before fitting the box. All data and annotations
 * use this projection; pan/zoom remain in screen pixels and never move labels
 * independently of their values. */
export function surfaceAxisProjection(
  camera: SurfaceCamera,
  stretch: Vector,
  width: number,
  height: number,
  fontSize: number,
): SurfaceProjection {
  const base = { ...camera, zoom: 1, panX: 0, panY: 0 };
  const raw = (f: number, r: number, z: number) =>
    surfaceProject(f, r, z, base, 3.7, 3.2, stretch);
  const pts = corners.map((p) => raw(...p));
  const xs = pts.map((p) => p.x),
    ys = pts.map((p) => p.y);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs),
    minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const left = Math.max(48, Math.min(fontSize * 5, width * 0.18)),
    right = Math.max(32, Math.min(fontSize * 3, width * 0.12));
  const top = Math.max(24, fontSize * 1.6),
    bottom = Math.max(30, Math.min(fontSize * 3.2, height * 0.22));
  const w = Math.max(12, width - left - right),
    h = Math.max(12, height - top - bottom);
  const unit =
    Math.min(w / Math.max(1e-9, maxX - minX), h / Math.max(1e-9, maxY - minY)) *
    0.96 *
    camera.zoom;
  return (f, r, z) => {
    const p = raw(f, r, z);
    return {
      x: left + w / 2 + (p.x - (minX + maxX) / 2) * unit + camera.panX,
      y: top + h / 2 + (p.y - (minY + maxY) / 2) * unit + camera.panY,
      depth: p.depth,
    };
  };
}

/** Same affine fitted-box projection for GPU vertices, axes and picking. */
export function surfaceProjectionMatrix(
  project: SurfaceProjection,
  width: number,
  height: number,
) {
  const depths = corners.map((p) => project(...p).depth);
  const minimum = Math.min(...depths),
    span = Math.max(1e-12, Math.max(...depths) - minimum);
  const ndc = (p: SurfacePoint) => [
    (2 * p.x) / Math.max(1, width) - 1,
    1 - (2 * p.y) / Math.max(1, height),
    0.98 - (1.96 * (p.depth - minimum)) / span,
  ];
  const origin = ndc(project(0, 0, 0));
  const basis = [
    ndc(project(1, 0, 0)),
    ndc(project(0, 1, 0)),
    ndc(project(0, 0, 1)),
  ];
  return new Float32Array([
    ...basis.flatMap((p) => [
      p[0] - origin[0],
      p[1] - origin[1],
      p[2] - origin[2],
      0,
    ]),
    ...origin,
    1,
  ]);
}

function niceValue(value: number, lower: number, upper: number) {
  if (value === 0) return 0;
  const power = 10 ** Math.floor(Math.log10(Math.abs(value)));
  const candidates = [1, 2, 2.5, 5, 10]
    .map((n) => Number((Math.sign(value) * n * power).toPrecision(14)))
    .filter((n) => n >= lower && n <= upper);
  return candidates.sort(
    (a, b) => Math.abs(a - value) - Math.abs(b - value),
  )[0];
}

/** Nice original-intensity values, placed by the SAME transfer as the mesh.
 * In log/√ views, rounding inverse-transformed intervals gives readable values
 * over the full height instead of clustering linear labels at the top. */
export function surfaceAxisTicks(
  minimum: number,
  maximum: number,
  intervals: number,
  scale: SurfaceScale = "linear",
  integer = false,
) {
  const lo = Math.min(minimum, maximum),
    hi = Math.max(minimum, maximum);
  let base = linearAxisTicks(lo, hi, intervals);
  if (base.ticks.length < 2 && hi > lo)
    base = linearAxisTicks(lo, hi, Math.max(3, intervals + 1));
  const formatting = linearAxisTicks(lo, hi, 3);
  let values = base.ticks.map((t) => t.value);
  if (scale !== "linear" && hi > lo) {
    values = [];
    const lower = scale === "sqrt" ? Math.sqrt(Math.max(0, lo)) : lo;
    const span =
      scale === "sqrt"
        ? Math.sqrt(Math.max(0, hi)) - lower
        : Math.log1p(hi - lo);
    for (let i = 0; i <= intervals; i++) {
      const raw =
        scale === "sqrt"
          ? (lower + (span * i) / intervals) ** 2
          : lo + Math.expm1((span * i) / intervals);
      const value = niceValue(
        raw - formatting.offset,
        (scale === "sqrt" ? Math.max(0, lo) : lo) - formatting.offset,
        hi - formatting.offset,
      );
      if (value != null) values.push(value + formatting.offset);
    }
  }
  if (integer) values = values.filter(Number.isInteger);
  if (integer && values.length < 2 && lo < hi)
    values = [Math.ceil(lo), Math.floor(hi)];
  if (integer && lo < hi) values.push(Math.ceil(lo), Math.floor(hi));
  if (lo === hi) values = [lo];
  const offset = formatting.offset,
    factor = formatting.scale;
  const directLog = scale === "log" && offset === 0 && lo >= 0;
  const logLabel = (value: number) => {
    if (!value || (value >= 0.001 && value < 1000))
      return String(Number(value.toPrecision(5)));
    const exponent = Math.floor(Math.log10(value));
    const mantissa = Number((value / 10 ** exponent).toPrecision(3));
    const power = String(exponent)
      .split("")
      .map((d) => (d === "-" ? "⁻" : "⁰¹²³⁴⁵⁶⁷⁸⁹"[Number(d)]))
      .join("");
    return `${mantissa === 1 ? "" : `${mantissa}×`}10${power}`;
  };
  const sortedValues = [...new Set(values)].sort((a, b) => a - b);
  const step = Math.min(
    ...sortedValues.slice(1).map((v, i) => (v - sortedValues[i]) / factor),
  );
  const digits = clamp(
    1 - Math.floor(Math.log10(Number.isFinite(step) && step > 0 ? step : 1)),
    0,
    12,
  );
  const ticks = sortedValues
    .map((value) => ({
      value,
      label: directLog
        ? logLabel(value)
        : String(Number(((value - offset) / factor).toFixed(digits))).replace(
            "-",
            "−",
          ),
      fraction:
        scale === "linear"
          ? lo === hi
            ? 0.5
            : (value - minimum) / (maximum - minimum)
          : surfaceIntensity(value, [lo, hi], scale),
    }))
    .filter((t) => Number.isFinite(t.fraction));
  return { ticks, annotation: directLog ? null : formatting.annotation };
}

/** Find a silhouette edge, so its outward tick marks and labels cannot cross
 * the projected data box. Prefer the lower floor edges; I uses the left edge.
 * Camera quadrants and top/front/right views share the same geometric rule. */
function axisEdge(kind: AxisKind, project: SurfaceProjection) {
  const dim = kind === "frame" ? 0 : kind === "radial" ? 1 : 2;
  const pts = corners.map((p) => project(...p));
  const center = {
    x: pts.reduce((n, p) => n + p.x, 0) / 8,
    y: pts.reduce((n, p) => n + p.y, 0) / 8,
  };
  const candidates = [];
  for (const origin of corners.filter((p) => p[dim] === 0)) {
    const other = [...origin] as Vector;
    other[dim] = 1;
    const start = project(...origin),
      end = project(...other);
    const dx = end.x - start.x,
      dy = end.y - start.y,
      length = Math.hypot(dx, dy);
    if (length < 24) continue;
    const middle = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
    let nx = -dy / length,
      ny = dx / length;
    if (nx * (middle.x - center.x) + ny * (middle.y - center.y) < 0) {
      nx = -nx;
      ny = -ny;
    }
    if (pts.some((p) => nx * (p.x - middle.x) + ny * (p.y - middle.y) > 1e-5))
      continue;
    const score =
      kind === "intensity"
        ? -middle.x
        : middle.y + (origin[2] === 0 ? 10000 : 0);
    candidates.push({
      origin,
      start,
      end,
      length,
      normal: [nx, ny] as [number, number],
      score,
    });
  }
  return candidates.sort((a, b) => b.score - a.score)[0] ?? null;
}

function labelBox(
  text: string,
  x: number,
  y: number,
  angle: number,
  fontSize: number,
  measure: (text: string) => number,
  axis: SurfaceAxisLabel["axis"],
  role: SurfaceAxisLabel["role"],
  value?: number,
): SurfaceAxisLabel {
  const width = measure(text),
    height = fontSize + 2;
  const w =
    Math.abs(Math.cos(angle)) * width + Math.abs(Math.sin(angle)) * height;
  const h =
    Math.abs(Math.sin(angle)) * width + Math.abs(Math.cos(angle)) * height;
  return {
    text,
    x,
    y,
    width,
    height,
    angle,
    axis,
    role,
    value,
    bounds: {
      left: x - w / 2 - 2,
      top: y - h / 2 - 2,
      right: x + w / 2 + 2,
      bottom: y + h / 2 + 2,
    },
  };
}
export function surfaceLabelCorners(label: SurfaceAxisLabel) {
  const c = Math.cos(label.angle),
    s = Math.sin(label.angle);
  return [-1, 1].flatMap((x) =>
    [-1, 1].map((y) => ({
      x:
        label.x +
        x * (label.width / 2 + 2) * c -
        y * (label.height / 2 + 2) * s,
      y:
        label.y +
        x * (label.width / 2 + 2) * s +
        y * (label.height / 2 + 2) * c,
    })),
  );
}
/** Oriented text boxes, not their oversized axis-aligned bounds: slanted titles
 * can remain beside their numbers without hiding perfectly readable ticks. */
export function surfaceLabelsOverlap(a: SurfaceAxisLabel, b: SurfaceAxisLabel) {
  const ac = surfaceLabelCorners(a),
    bc = surfaceLabelCorners(b);
  for (const angle of [
    a.angle,
    a.angle + Math.PI / 2,
    b.angle,
    b.angle + Math.PI / 2,
  ]) {
    const x = Math.cos(angle),
      y = Math.sin(angle);
    const ap = ac.map((p) => p.x * x + p.y * y),
      bp = bc.map((p) => p.x * x + p.y * y);
    if (
      Math.max(...ap) + 2 < Math.min(...bp) ||
      Math.max(...bp) + 2 < Math.min(...ap)
    )
      return false;
  }
  return true;
}

export function layoutSurfaceAxes(opts: {
  project: SurfaceProjection;
  width: number;
  height: number;
  fontSize: number;
  measure: (text: string) => number;
  frames: [number, number];
  radial: [number, number];
  radialTitle: string;
  limits: [number, number];
  scale: SurfaceScale;
}) {
  const { project, width, height, fontSize, measure } = opts;
  const axes: SurfaceAxis[] = [];
  const labels: SurfaceAxisLabel[] = [];
  const grids: [SurfacePoint, SurfacePoint][] = [];
  const canAdd = (label: SurfaceAxisLabel, extra: SurfaceAxisLabel[] = []) => {
    const b = label.bounds;
    if (
      b.left < 3 ||
      b.right > width - 3 ||
      b.top < 3 ||
      b.bottom > height - 3 ||
      [...labels, ...extra].some((l) => surfaceLabelsOverlap(label, l))
    )
      return false;
    return true;
  };
  const add = (label: SurfaceAxisLabel) => {
    if (!canAdd(label)) return false;
    labels.push(label);
    return true;
  };
  const intensityAnnotation = surfaceAxisTicks(
    ...opts.limits,
    3,
    opts.scale,
  ).annotation;
  const fullLegend = [
    `Intensity · ${opts.scale === "sqrt" ? "√" : opts.scale}`,
    intensityAnnotation,
  ]
    .filter(Boolean)
    .join("  ");
  const legend =
    [
      fullLegend,
      fullLegend.replace("Intensity", "I"),
      ["I", intensityAnnotation].filter(Boolean).join("  "),
    ].find((text) => measure(text) <= width - 16) ?? "I";
  add(
    labelBox(
      legend,
      8 + measure(legend) / 2,
      fontSize / 2 + 7,
      0,
      fontSize,
      measure,
      "legend",
      "legend",
    ),
  );
  for (const kind of ["frame", "radial", "intensity"] as const) {
    const edge = axisEdge(kind, project);
    if (!edge) continue;
    const range =
      kind === "frame"
        ? opts.frames
        : kind === "radial"
          ? opts.radial
          : opts.limits;
    const intervals = clamp(
      Math.floor(
        edge.length / (kind === "intensity" ? fontSize * 2.6 : fontSize * 4.2),
      ),
      2,
      6,
    );
    const ticks = surfaceAxisTicks(
      ...range,
      intervals,
      kind === "intensity" ? opts.scale : "linear",
      kind === "frame",
    );
    if (kind === "intensity")
      for (const tick of ticks.ticks)
        tick.fraction = surfaceIntensity(tick.value, range, opts.scale);
    // A modest radial offset (e.g. 20.00025°) is clearer as a short actual
    // coordinate than a long offset caption competing with a compact axis.
    if (kind === "radial" && ticks.annotation?.match(/[+−]/)) {
      const direct = ticks.ticks.map((t) =>
        String(Number(t.value.toPrecision(12))),
      );
      if (
        direct.every((text) => text.length <= 9) &&
        new Set(direct).size === direct.length
      ) {
        ticks.annotation = null;
        ticks.ticks.forEach((tick, i) => {
          tick.label = direct[i];
        });
      }
    }
    const title = [
      kind === "frame" ? "Frame" : kind === "radial" ? opts.radialTitle : "I",
      kind === "intensity" ? null : ticks.annotation,
    ]
      .filter(Boolean)
      .join("  ");
    const axis: SurfaceAxis = {
      kind,
      start: edge.start,
      end: edge.end,
      normal: edge.normal,
      title,
      ticks: [],
    };
    const [nx, ny] = edge.normal;
    const point = (t: number) => ({
      x: edge.start.x + (edge.end.x - edge.start.x) * t,
      y: edge.start.y + (edge.end.y - edge.start.y) * t,
      depth: 0,
    });
    let widest = 0;
    for (const tick of ticks.ticks) {
      const p = point(tick.fraction),
        end = { ...p, x: p.x + nx * 5, y: p.y + ny * 5 };
      axis.ticks.push({ ...tick, point: p, end, visible: false });
      widest = Math.max(
        widest,
        (Math.abs(nx) * measure(tick.label)) / 2 +
          (Math.abs(ny) * (fontSize + 2)) / 2,
      );
      // The grid has the very same physical tick positions as the labels.
      if (kind === "frame")
        grids.push([
          project(tick.fraction, 0, 0),
          project(tick.fraction, 1, 0),
        ]);
      else if (kind === "radial")
        grids.push([
          project(0, tick.fraction, 0),
          project(1, tick.fraction, 0),
        ]);
      else {
        const [f, r] = edge.origin;
        grids.push([
          project(f, r, tick.fraction),
          project(1 - f, r, tick.fraction),
        ]);
        grids.push([
          project(f, r, tick.fraction),
          project(f, 1 - r, tick.fraction),
        ]);
      }
    }
    let angle = Math.atan2(
      edge.end.y - edge.start.y,
      edge.end.x - edge.start.x,
    );
    if (angle > Math.PI / 2) angle -= Math.PI;
    if (angle < -Math.PI / 2) angle += Math.PI;
    const offset = 5 + 7 + 2 * widest + 8 + (fontSize + 2) / 2;
    const titleCandidates: { label: SurfaceAxisLabel; visibleTicks: number }[] =
      [];
    for (const distance of [
      offset,
      offset - 6,
      offset - 12,
      Math.max(20, offset - 20),
      20,
    ]) {
      for (const fraction of [0.5, 0.25, 0.75, 0.1, 0.9, 0, 1, -0.1, 1.1]) {
        const p = point(fraction);
        const label = labelBox(
          title,
          p.x + nx * distance,
          p.y + ny * distance,
          angle,
          fontSize,
          measure,
          kind,
          "title",
        );
        if (!canAdd(label)) continue;
        const occupied = [label];
        for (const tick of axis.ticks) {
          const extent =
            (Math.abs(nx) * measure(tick.label)) / 2 +
            (Math.abs(ny) * (fontSize + 2)) / 2;
          const d = 5 + 6 + extent;
          const number = labelBox(
            tick.label,
            tick.point.x + nx * d,
            tick.point.y + ny * d,
            0,
            fontSize,
            measure,
            kind,
            "tick",
            tick.value,
          );
          if (canAdd(number, occupied)) occupied.push(number);
        }
        titleCandidates.push({ label, visibleTicks: occupied.length - 1 });
      }
    }
    const chosen = titleCandidates.sort(
      (a, b) => b.visibleTicks - a.visibleTicks,
    )[0];
    if (chosen) add(chosen.label);
    axes.push(axis);
  }
  // Reserve titles first; then choose only tick labels that fit, including at
  // shared corners. Never clamp labels onto the image or onto one another.
  for (const axis of axes)
    for (const tick of axis.ticks) {
      const [nx, ny] = axis.normal;
      const extent =
        (Math.abs(nx) * measure(tick.label)) / 2 +
        (Math.abs(ny) * (fontSize + 2)) / 2;
      const offset = 5 + 6 + extent;
      tick.visible = add(
        labelBox(
          tick.label,
          tick.point.x + nx * offset,
          tick.point.y + ny * offset,
          0,
          fontSize,
          measure,
          axis.kind,
          "tick",
          tick.value,
        ),
      );
    }
  return { axes, labels, grids };
}

export function drawSurfaceAxes(
  ctx: CanvasRenderingContext2D,
  layout: ReturnType<typeof layoutSurfaceAxes>,
  color: string,
) {
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 1;
  for (const axis of layout.axes) {
    ctx.beginPath();
    ctx.moveTo(axis.start.x, axis.start.y);
    ctx.lineTo(axis.end.x, axis.end.y);
    ctx.stroke();
    for (const tick of axis.ticks) {
      ctx.beginPath();
      ctx.moveTo(tick.point.x, tick.point.y);
      ctx.lineTo(tick.end.x, tick.end.y);
      ctx.stroke();
    }
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const label of layout.labels) {
    ctx.save();
    ctx.translate(label.x, label.y);
    ctx.rotate(label.angle);
    ctx.fillText(label.text, 0, 0);
    ctx.restore();
  }
}

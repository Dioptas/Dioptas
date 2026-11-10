import type { Pattern, Unit } from "./types";
import type { PlotRange } from "./usePlotNavigation";
import { unitLabel } from "./types";
import { visibleSamples } from "./patternSamples";
import { linearAxisTicks, linearTicks, logTicks } from "./plotTicks";
import { scalePhaseLines } from "./phaseLineScaling";
import { SvgRecording } from "./plotFigureExport";

export type FigureCurve = {
  id: string;
  name: string;
  color: string;
  x: number[];
  y: (number | null)[];
};
export type PatternFigureSource = {
  curves: FigureCurve[];
  phases: NonNullable<Pattern["phaseLines"]>;
  pattern: Pattern;
  unit: Unit;
  view: PlotRange;
  scale: "linear" | "log" | "sqrt";
};
export type CurveStyle = {
  id: string;
  label: string;
  color: string;
  visible: boolean;
  width: number;
  style: "line" | "dash" | "points" | "both";
};
export type PhaseStyle = {
  id: string;
  label: string;
  color: string;
  visible: boolean;
};
export type PatternFigureOptions = {
  width: number;
  height: number;
  fontSize: number;
  font: "Arial" | "Times New Roman" | "Helvetica";
  title: string;
  xLabel: string;
  yLabel: string;
  theme: "white" | "transparent" | "dark";
  legend:
    | "auto"
    | "top-left"
    | "top-right"
    | "bottom-left"
    | "bottom-right"
    | "above"
    | "below"
    | "right"
    | "none";
  phases: "plot" | "rows" | "none";
  grid: boolean;
  box: boolean;
  yTicks: boolean;
  tickDirection: "in" | "out";
  range: "view" | "full" | "custom";
  xMin: number;
  xMax: number;
  yRange: "view" | "auto" | "custom";
  yMin: number;
  yMax: number;
  scale: PatternFigureSource["scale"];
  curves: CurveStyle[];
  phaseStyles: PhaseStyle[];
};
export type PatternFigureSettings = {
  options: PatternFigureOptions;
  format: "svg" | "png";
  dpi: number;
};
export const phaseId = (line: PatternFigureSource["phases"][number]) =>
  String(line.phaseIndex ?? `${line.name}:${line.color}`);
const phaseGroups = (source: PatternFigureSource) => [
  ...new Map(source.phases.map((line) => [phaseId(line), line])).values(),
];
const inverse = (y: number, scale: PatternFigureSource["scale"]) =>
  scale === "log" ? 10 ** y : scale === "sqrt" ? Math.max(0, y) ** 2 : y;
const colorForPaper = (color: string) =>
  /^#(?:f{6}|e{6}|d{6})$/i.test(color) ? "#202124" : color;
export function defaultPatternFigureSettings(
  source: PatternFigureSource,
  format: "svg" | "png" = "svg",
): PatternFigureSettings {
  return {
    format,
    dpi: 300,
    options: {
      width: 180,
      height: 115,
      fontSize: 10,
      font: "Arial",
      title: "",
      xLabel: unitLabel(source.unit),
      yLabel: "Intensity (a.u.)",
      theme: "white",
      legend: "auto",
      phases: source.phases.length ? "rows" : "none",
      grid: false,
      box: true,
      yTicks: true,
      tickDirection: "in",
      range: "view",
      xMin: source.view.xMin,
      xMax: source.view.xMax,
      yRange: "view",
      yMin: inverse(source.view.yMin, source.scale),
      yMax: inverse(source.view.yMax, source.scale),
      scale: source.scale,
      curves: source.curves.map((curve) => ({
        id: curve.id,
        label: curve.name,
        color: colorForPaper(curve.color),
        visible: true,
        width: 1,
        style: "line",
      })),
      phaseStyles: phaseGroups(source).map((line) => ({
        id: phaseId(line),
        label: line.name,
        color: colorForPaper(line.color),
        visible: true,
      })),
    },
  };
}
const storageKey = "dioptas-pattern-figure-v1";
const signature = (source: PatternFigureSource) =>
  JSON.stringify([
    source.unit,
    source.curves.map((c) => [c.id, c.name]),
    phaseGroups(source).map((line) => [phaseId(line), line.name]),
  ]);
export function rememberPatternFigure(
  source: PatternFigureSource,
  settings: PatternFigureSettings,
) {
  try {
    localStorage.setItem(
      storageKey,
      JSON.stringify({ version: 1, signature: signature(source), settings }),
    );
  } catch {
    /* Optional appearance preferences. */
  }
}
export function restorePatternFigure(
  source: PatternFigureSource,
  format?: "svg" | "png",
): PatternFigureSettings {
  const defaults = defaultPatternFigureSettings(source, format ?? "svg");
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) ?? "null");
    if (saved?.version !== 1 || !saved.settings?.options) return defaults;
    // Labels, visibility, colors and custom ranges belong to this named plot.
    // Other plots inherit only reusable layout/style settings.
    const old = saved.settings.options;
    const same = saved.signature === signature(source);
    const settings: PatternFigureSettings = {
      format: format ?? saved.settings.format,
      dpi: saved.settings.dpi,
      options: {
        ...defaults.options,
        ...old,
        ...(same
          ? {}
          : {
              curves: defaults.options.curves,
              phaseStyles: defaults.options.phaseStyles,
              title: "",
              xLabel: defaults.options.xLabel,
              yLabel: defaults.options.yLabel,
              range: "view",
              yRange: "view",
              scale: source.scale,
            }),
      },
    };
    if (!same && settings.options.theme === "dark")
      settings.options.curves = settings.options.curves.map((c) => ({
        ...c,
        color: c.color === "#202124" ? "#ffffff" : c.color,
      }));
    validatePatternFigure(source, settings.options);
    if (
      !["svg", "png"].includes(settings.format) ||
      ![150, 300, 600].includes(settings.dpi)
    )
      return defaults;
    return settings;
  } catch {
    return defaults;
  }
}
const finiteBetween = (v: number, min: number, max: number) =>
  Number.isFinite(v) && v >= min && v <= max;
export function validatePatternFigure(
  source: PatternFigureSource,
  o: PatternFigureOptions,
) {
  if (!finiteBetween(o.width, 50, 400) || !finiteBetween(o.height, 45, 400))
    throw Error("Use a width of 50–400 mm and a height of 45–400 mm.");
  if (!finiteBetween(o.fontSize, 6, 24))
    throw Error("Use a font size of 6–24 pt.");
  if (
    !["Arial", "Times New Roman", "Helvetica"].includes(o.font) ||
    !["white", "transparent", "dark"].includes(o.theme) ||
    !["linear", "log", "sqrt"].includes(o.scale)
  )
    throw Error("Choose a valid figure appearance.");
  if (
    ![
      "auto",
      "top-left",
      "top-right",
      "bottom-left",
      "bottom-right",
      "above",
      "below",
      "right",
      "none",
    ].includes(o.legend) ||
    !["plot", "rows", "none"].includes(o.phases) ||
    !["view", "full", "custom"].includes(o.range) ||
    !["view", "auto", "custom"].includes(o.yRange) ||
    !["in", "out"].includes(o.tickDirection)
  )
    throw Error("Choose valid axis and legend settings.");
  if (
    ![o.title, o.xLabel, o.yLabel].every(
      (s) => typeof s === "string" && s.length <= 240,
    )
  )
    throw Error("Keep titles and axis labels within 240 characters.");
  if (![o.grid, o.box, o.yTicks].every((value) => typeof value === "boolean"))
    throw Error("Choose valid axis display settings.");
  if (
    !Array.isArray(o.curves) ||
    !o.curves.length ||
    !o.curves.some((c) => c.visible)
  )
    throw Error("Show at least one measured curve.");
  const ids = new Set<string>();
  for (const c of o.curves) {
    if (
      ids.has(c.id) ||
      !source.curves.some((s) => s.id === c.id) ||
      !/^#[0-9a-f]{6}$/i.test(c.color) ||
      !finiteBetween(c.width, 0.2, 5) ||
      typeof c.label !== "string" ||
      c.label.length > 240 ||
      typeof c.visible !== "boolean" ||
      !["line", "dash", "points", "both"].includes(c.style)
    )
      throw Error("Use valid curve labels, colors and line widths (0.2–5 pt).");
    ids.add(c.id);
  }
  if (!Array.isArray(o.phaseStyles))
    throw Error("Choose valid phase references.");
  const phaseIds = new Set(phaseGroups(source).map(phaseId));
  const seenPhases = new Set<string>();
  for (const p of o.phaseStyles) {
    if (seenPhases.has(p.id))
      throw Error("A phase can appear only once in the figure settings.");
    seenPhases.add(p.id);
    if (
      !phaseIds.has(p.id) ||
      !/^#[0-9a-f]{6}$/i.test(p.color) ||
      typeof p.label !== "string" ||
      p.label.length > 240 ||
      typeof p.visible !== "boolean"
    )
      throw Error("Use valid phase labels and colors.");
  }
  if (
    o.range === "custom" &&
    (![o.xMin, o.xMax].every(Number.isFinite) || o.xMin >= o.xMax)
  )
    throw Error("The horizontal minimum must be smaller than the maximum.");
  if (
    o.yRange === "custom" &&
    (![o.yMin, o.yMax].every(Number.isFinite) || o.yMin >= o.yMax)
  )
    throw Error("The intensity minimum must be smaller than the maximum.");
}

/** A paper figure reads the same displayed samples. No integration, interpolation,
 * unit conversion, offset or normalization is performed by this renderer. */
export function renderPatternFigure(
  source: PatternFigureSource,
  o: PatternFigureOptions,
): string {
  validatePatternFigure(source, o);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round((o.width * 72) / 25.4);
  canvas.height = Math.round((o.height * 72) / 25.4);
  const recording = new SvgRecording(canvas),
    ctx = recording.context;
  const W = canvas.width,
    H = canvas.height,
    fs = o.fontSize;
  const ink = o.theme === "dark" ? "#e5e9ed" : "#202124",
    paper = o.theme === "dark" ? "#101518" : "#ffffff";
  if (o.theme !== "transparent") {
    ctx.fillStyle = paper;
    ctx.fillRect(0, 0, W, H);
  }
  ctx.font = `${fs}px ${o.font}`;
  ctx.textBaseline = "middle";
  const styles = o.curves.filter((s) => s.visible);
  const curves = styles.map((style) => ({
    ...source.curves.find((c) => c.id === style.id)!,
    ...style,
  }));
  const phases = o.phaseStyles.filter(
    (p) => p.visible && source.phases.some((line) => phaseId(line) === p.id),
  );
  const extent = (values: Iterable<number>) => {
    let min = Infinity,
      max = -Infinity;
    for (const v of values)
      if (Number.isFinite(v)) {
        min = Math.min(min, v);
        max = Math.max(max, v);
      }
    return [min, max];
  };
  let [xmin, xmax] =
    o.range === "view"
      ? [source.view.xMin, source.view.xMax]
      : o.range === "custom"
        ? [o.xMin, o.xMax]
        : extent(curves.flatMap((c) => c.x));
  if (!Number.isFinite(xmin) || !Number.isFinite(xmax) || xmin >= xmax)
    throw Error("The selected curves need a finite horizontal range.");
  const transform = (y: number) =>
    o.scale === "log"
      ? y > 0
        ? Math.log10(y)
        : NaN
      : o.scale === "sqrt"
        ? Math.sqrt(Math.max(0, y))
        : y;
  const ys: number[] = [];
  for (const curve of curves) {
    const [start, end] = visibleSamples(curve.x, xmin, xmax);
    for (let i = start; i < end; i++)
      if (curve.y[i] != null) ys.push(transform(curve.y[i]!));
  }
  if (!ys.some(Number.isFinite))
    throw Error(
      o.scale === "log"
        ? "This range needs positive intensities for a log axis."
        : "The selected range has no plottable samples.",
    );
  let [ymin, ymax] =
    o.yRange === "view"
      ? o.scale === source.scale
        ? [source.view.yMin, source.view.yMax]
        : [
            transform(inverse(source.view.yMin, source.scale)),
            transform(inverse(source.view.yMax, source.scale)),
          ]
      : o.yRange === "custom"
        ? [transform(o.yMin), transform(o.yMax)]
        : extent(ys);
  if (o.yRange === "custom" && o.scale === "sqrt" && o.yMin < 0)
    throw Error("Square-root axis limits must be nonnegative.");
  if (o.yRange === "auto") {
    const pad = Math.max((ymax - ymin) * 0.05, Math.abs(ymax) * 1e-5, 1e-6);
    ymin -= pad;
    ymax += pad;
  }
  if (![ymin, ymax].every(Number.isFinite) || ymin >= ymax)
    throw Error(
      "Choose finite, increasing intensity limits; log limits must be positive and √ limits nonnegative.",
    );
  const yAxis =
    o.scale === "log"
      ? { ticks: logTicks(ymin, ymax, 5), annotation: null }
      : linearAxisTicks(
          o.scale === "sqrt" ? Math.max(0, ymin) ** 2 : ymin,
          o.scale === "sqrt" ? ymax ** 2 : ymax,
          5,
        );
  const yt = yAxis.ticks.map((t) => ({
    ...t,
    value: o.scale === "sqrt" ? transform(t.value) : t.value,
  }));
  const tickWidth = o.yTicks
    ? Math.max(0, ...yt.map((t) => ctx.measureText(t.label).width))
    : 0;
  const L = Math.max(fs * 3.1, tickWidth + fs * 3),
    baseRight = fs * 1.5;
  const lineHeight = fs * 1.5;
  const legendItems = [
    ...curves.map((c) => ({
      label: c.label,
      color: c.color,
      dash: c.style === "dash",
      points: c.style === "points" || c.style === "both",
      line: c.style !== "points",
      width: c.width,
    })),
    ...(o.phases === "plot"
      ? phases.map((p) => ({
          label: p.label,
          color: p.color,
          dash: false,
          points: false,
          line: true,
          width: 0.8,
        }))
      : []),
  ];
  const legendActive = o.legend !== "none" && legendItems.length > 0;
  const wrap = (text: string, width: number) => {
    const lines: string[] = [];
    let line = "";
    for (const ch of Array.from(text)) {
      if (line && ctx.measureText(line + ch).width > width) {
        lines.push(line);
        line = "";
      }
      line += ch;
    }
    lines.push(line);
    return lines;
  };
  const horizontalLegend = o.legend === "above" || o.legend === "below";
  const legendColumns = horizontalLegend && W - L - baseRight > fs * 28 ? 2 : 1;
  const legendWidth = horizontalLegend
    ? W - L - baseRight
    : Math.min(
        W * 0.31,
        Math.max(
          fs * 8,
          ...legendItems.map((c) => ctx.measureText(c.label).width + fs * 3),
        ),
      );
  const legendLines = legendItems.map((c) =>
    wrap(c.label, legendWidth / legendColumns - fs * 3),
  );
  const legendRowHeights: number[] = [];
  for (let i = 0; i < legendItems.length; i += legendColumns)
    legendRowHeights.push(
      Math.max(
        ...legendLines.slice(i, i + legendColumns).map((lines) => lines.length),
      ) * lineHeight,
    );
  const legendHeight =
    legendRowHeights.reduce((sum, height) => sum + height, 0) + fs;
  const titleLines = o.title ? wrap(o.title, W - L - baseRight) : [];
  const titleHeight = titleLines.length * lineHeight;
  const above = legendActive && o.legend === "above" ? legendHeight + fs : 0;
  const below = legendActive && o.legend === "below" ? legendHeight + fs : 0;
  const top = fs * 1.7 + titleHeight + above;
  const R =
    W -
    baseRight -
    (legendActive && o.legend === "right" ? legendWidth + fs : 0);
  const rowHeight = fs * 3;
  const rowsHeight =
    o.phases === "rows"
      ? phases.length * rowHeight + (phases.length ? fs : 0)
      : 0;
  const bottom = H - fs * 4.3 - rowsHeight - below;
  if (R - L < fs * 9 || bottom - top < fs * 7)
    throw Error(
      "Increase the figure size, reduce the font size, or move/hide the legend to leave room for the plot.",
    );
  const w = R - L,
    h = bottom - top;
  if (
    ctx.measureText(o.xLabel).width > w ||
    ctx.measureText(o.yLabel).width > h
  )
    throw Error(
      "Shorten the axis label, reduce the font size, or increase the figure size to fit the labels.",
    );
  const px = (x: number) => L + ((x - xmin) / (xmax - xmin)) * w,
    py = (y: number) => bottom - ((y - ymin) / (ymax - ymin)) * h;
  const line = (
    x0: number,
    y0: number,
    x1: number,
    y1: number,
    color = ink,
    width = 0.65,
  ) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
  };
  const text = (
    s: string,
    x: number,
    y: number,
    align: CanvasTextAlign = "left",
    color = ink,
  ) => {
    ctx.textAlign = align;
    ctx.fillStyle = color;
    ctx.fillText(s, x, y);
  };
  titleLines.forEach((s, i) =>
    text(s, (L + R) / 2, fs + i * lineHeight, "center"),
  );
  let intervals = Math.max(2, Math.floor(w / (fs * 5)));
  let xt = linearTicks(xmin, xmax, intervals);
  while (
    intervals > 1 &&
    xt.length > 1 &&
    ((xt[1].value - xt[0].value) / (xmax - xmin)) * w <
      Math.max(...xt.map((t) => ctx.measureText(t.label).width)) + fs
  )
    xt = linearTicks(xmin, xmax, --intervals);
  if (o.grid) {
    for (const t of xt)
      line(
        px(t.value),
        top,
        px(t.value),
        bottom,
        o.theme === "dark" ? "#39434d" : "#dddddd",
        0.4,
      );
    for (const t of yt)
      line(
        L,
        py(t.value),
        R,
        py(t.value),
        o.theme === "dark" ? "#39434d" : "#dddddd",
        0.4,
      );
  }
  ctx.save();
  ctx.beginPath();
  ctx.rect(L, top, w, h);
  ctx.clip();
  // Measured sample order (including descending d) and gaps are preserved.
  const occupied: { x: number; y: number }[] = [];
  for (const curve of curves) {
    ctx.strokeStyle = curve.color;
    ctx.fillStyle = curve.color;
    ctx.lineWidth = curve.width;
    ctx.setLineDash(
      curve.style === "dash" ? [4 * curve.width, 2 * curve.width] : [],
    );
    ctx.beginPath();
    let previous = false;
    const [start, end] = visibleSamples(curve.x, xmin, xmax);
    for (let i = start; i < end; i++) {
      const x = curve.x[i],
        y = curve.y[i],
        value = y == null ? NaN : transform(y);
      if (!Number.isFinite(x) || !Number.isFinite(value)) {
        previous = false;
        continue;
      }
      const xx = px(x),
        yy = py(value);
      occupied.push({ x: xx, y: yy });
      if (previous) ctx.lineTo(xx, yy);
      else ctx.moveTo(xx, yy);
      previous = true;
    }
    if (curve.style !== "points") ctx.stroke();
    if (curve.style === "points" || curve.style === "both") {
      for (let i = start; i < end; i++) {
        const x = curve.x[i],
          y = curve.y[i],
          value = y == null ? NaN : transform(y);
        if (Number.isFinite(x) && Number.isFinite(value))
          ctx.fillRect(
            px(x) - curve.width,
            py(value) - curve.width,
            curve.width * 2,
            curve.width * 2,
          );
      }
    }
  }
  ctx.setLineDash([]);
  if (o.phases === "plot") {
    const lines = source.phases.filter((l) =>
      phases.some((p) => p.id === phaseId(l)),
    );
    const tops = scalePhaseLines(
      source.pattern,
      lines,
      { xMin: xmin, xMax: xmax, yMin: ymin, yMax: ymax },
      transform,
    );
    for (const [i, reference] of lines.entries())
      if (reference.x >= xmin && reference.x <= xmax)
        line(
          px(reference.x),
          bottom,
          px(reference.x),
          py(tops[i]),
          phases.find((p) => p.id === phaseId(reference))!.color,
          0.8,
        );
  }
  ctx.restore();
  const axisBottom = bottom + rowsHeight;
  line(L, top, L, bottom);
  line(L, axisBottom, R, axisBottom);
  if (o.box) {
    line(L, top, R, top);
    line(R, top, R, axisBottom);
  }
  const tickSize = fs * 0.4 * (o.tickDirection === "in" ? -1 : 1);
  for (const t of xt) {
    const x = px(t.value);
    line(x, axisBottom, x, axisBottom + tickSize);
    const halfLabel = ctx.measureText(t.label).width / 2;
    text(
      t.label,
      Math.max(halfLabel + 2, Math.min(W - halfLabel - 2, x)),
      axisBottom + fs * 1.3,
      "center",
    );
    if (o.box) line(x, top, x, top - tickSize);
  }
  for (const t of yt) {
    const y = py(t.value);
    line(L, y, L - tickSize, y);
    if (o.yTicks) text(t.label, L - fs * 0.65, y, "right");
    if (o.box) line(R, y, R + tickSize, y);
  }
  if (yAxis.annotation && o.yTicks) text(yAxis.annotation, L, top - fs * 0.75);
  text(o.xLabel, (L + R) / 2, axisBottom + fs * 3, "center");
  ctx.save();
  ctx.translate(fs * 0.9, (top + bottom) / 2);
  ctx.rotate(-Math.PI / 2);
  text(o.yLabel, 0, 0, "center");
  ctx.restore();
  if (o.phases === "rows") {
    for (const [i, phase] of phases.entries()) {
      const y = bottom + fs + (i + 1) * rowHeight;
      const references = source.phases.filter(
        (l) => phaseId(l) === phase.id && l.x >= xmin && l.x <= xmax,
      );
      const maximum = Math.max(1e-20, ...references.map((l) => l.intensity));
      line(L, y, R, y, o.theme === "dark" ? "#65717d" : "#c5c5c5", 0.35);
      for (const ref of references)
        line(
          px(ref.x),
          y,
          px(ref.x),
          y - (Math.max(0, ref.intensity) / maximum) * rowHeight * 0.45,
          phase.color,
          0.8,
        );
      const labelLines = wrap(phase.label, w * 0.6);
      if (labelLines.length > 1)
        throw Error(
          "Shorten the phase label or use a wider figure for separate reference rows.",
        );
      text(
        phase.label,
        R - fs * 0.5,
        y - rowHeight * 0.8,
        "right",
        phase.color,
      );
    }
  }
  if (legendActive) {
    let x = R - legendWidth - fs * 0.5,
      y = top + fs * 0.5;
    if (o.legend.includes("left")) x = L + fs * 0.5;
    if (o.legend.includes("bottom")) y = bottom - legendHeight - fs * 0.5;
    if (o.legend === "above") {
      x = L;
      y = top - above;
    }
    if (o.legend === "below") {
      x = L;
      y = axisBottom + fs * 4;
    }
    if (o.legend === "right") {
      x = R + fs;
      y = top;
    }
    if (
      ["auto", "top-left", "top-right", "bottom-left", "bottom-right"].includes(
        o.legend,
      ) &&
      (legendWidth > w || legendHeight > h)
    )
      throw Error(
        "The legend does not fit inside the axes. Move it outside or increase the figure size.",
      );
    if (o.legend === "right" && legendHeight > h)
      throw Error(
        "The legend is taller than the plot. Increase the figure height or hide some entries.",
      );
    if (o.legend === "auto") {
      const candidates = [
        [R - legendWidth - fs * 0.5, top + fs * 0.5],
        [L + fs * 0.5, top + fs * 0.5],
        [R - legendWidth - fs * 0.5, bottom - legendHeight - fs * 0.5],
        [L + fs * 0.5, bottom - legendHeight - fs * 0.5],
      ];
      [x, y] = candidates.reduce((best, candidate) => {
        const score = ([cx, cy]: number[]) =>
          occupied.filter(
            (p) =>
              p.x >= cx &&
              p.x <= cx + legendWidth &&
              p.y >= cy &&
              p.y <= cy + legendHeight,
          ).length;
        return score(candidate) < score(best) ? candidate : best;
      });
    }
    // Legend has an opaque paper backing on solid paper; transparent figures
    // keep a transparent legend, suitable for placing over another background.
    if (o.theme !== "transparent") {
      ctx.fillStyle = paper;
      ctx.fillRect(x, y, legendWidth, legendHeight);
    }
    const legendX = x,
      legendY = y;
    for (const [i, item] of legendItems.entries()) {
      const column = horizontalLegend ? i % legendColumns : 0;
      const row = horizontalLegend ? Math.floor(i / legendColumns) : i;
      const itemX = legendX + (column * legendWidth) / legendColumns;
      const itemY =
        legendY +
        legendRowHeights.slice(0, row).reduce((sum, height) => sum + height, 0);
      const cy = itemY + fs * 0.75;
      ctx.setLineDash(item.dash ? [4 * item.width, 2 * item.width] : []);
      if (item.line)
        line(itemX + fs * 0.4, cy, itemX + fs * 2, cy, item.color, item.width);
      if (item.points) {
        ctx.fillStyle = item.color;
        ctx.fillRect(
          itemX + fs * 1.2 - item.width,
          cy - item.width,
          item.width * 2,
          item.width * 2,
        );
      }
      ctx.setLineDash([]);
      legendLines[i].forEach((label, j) =>
        text(label, itemX + fs * 2.7, cy + j * lineHeight, "left", ink),
      );
    }
  }
  return recording.svg(`${o.width}mm`, `${o.height}mm`);
}

/** Rasterize the same SVG used by the editor; DPI affects PNG only. */
export async function patternFigurePng(
  svg: string,
  width: number,
  height: number,
  dpi: number,
): Promise<string> {
  if (![150, 300, 600].includes(dpi))
    throw Error("Choose 150, 300 or 600 dpi.");
  const w = Math.round((width / 25.4) * dpi),
    h = Math.round((height / 25.4) * dpi);
  if (w * h > 40_000_000)
    throw Error(
      "The PNG exceeds 40 megapixels. Reduce its size or resolution.",
    );
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    canvas.getContext("2d")!.drawImage(image, 0, 0, w, h);
    return canvas.toDataURL("image/png").split(",")[1];
  } finally {
    URL.revokeObjectURL(url);
  }
}

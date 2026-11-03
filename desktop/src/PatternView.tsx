import { useEffect, useRef, useState } from "react";
import type { Pattern } from "./types";
import type { PatternHover } from "./plotReadout";
import { unitLabel } from "./types";
import { linearAxisTicks, linearTicks, logTicks } from "./plotTicks";
import { PlotZoomControls } from "./PlotZoomControls";
import { OverlayPlotLegend } from "./OverlayPlotLegend";
import {
  usePlotNavigation,
  usePlotWheel,
  type ZoomMode,
} from "./usePlotNavigation";

const extent = (values: number[]) =>
  values.reduce(
    ([low, high], value) =>
      Number.isFinite(value)
        ? [Math.min(low, value), Math.max(high, value)]
        : [low, high],
    [Infinity, -Infinity],
  );
const paddedExtent = (values: number[]): [number, number] => {
  const [lower, upper] = extent(values);
  const padding = Math.max(
    (upper - lower) * 0.04,
    Math.abs(lower) * 1e-6,
    1e-6,
  );
  return [lower - padding, upper + padding];
};
type PatternRegion = {
  name: string;
  min: number;
  max: number;
  color: string;
  active?: boolean;
};
const EMPTY_REGIONS: PatternRegion[] = [];

export function PatternView({
  pattern,
  patternColor = "#ffffff",
  showPattern = true,
  emphasizePattern = false,
  log,
  sqrt = false,
  antialias = true,
  autoRange = false,
  onAutoRange,
  zoomMode = "rectangle",
  onZoomMode,
  onPick,
  onHover,
  hoverHint,
  linkedPosition,
  activeRing,
  calibrantLines = [],
  showNumbers = false,
  overlayLegend,
  curves = [],
  referenceLines = [],
  regions = EMPTY_REGIONS,
  editRegions = false,
  onRegionChange,
}: {
  pattern: Pattern;
  patternColor?: string;
  showPattern?: boolean;
  emphasizePattern?: boolean;
  log: boolean;
  sqrt?: boolean;
  antialias?: boolean;
  autoRange?: boolean;
  onAutoRange?: (enabled: boolean) => void;
  zoomMode?: ZoomMode;
  onZoomMode?: (mode: ZoomMode) => void;
  onPick?: (x: number) => void;
  onHover?: (point: PatternHover | null) => void;
  hoverHint?: string;
  linkedPosition?: number;
  activeRing?: number;
  calibrantLines?: { x: number; ring: number }[];
  showNumbers?: boolean;
  overlayLegend?: { name: string; color: string }[];
  curves?: NonNullable<Pattern["curves"]>;
  referenceLines?: NonNullable<Pattern["phaseLines"]>;
  regions?: PatternRegion[];
  editRegions?: boolean;
  onRegionChange?: (name: string, min: number, max: number) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    container = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 900, height: 230 });
  const [left, setLeft] = useState(76);
  const regionDrag = useRef<{
    name: string;
    mode: "min" | "max" | "move";
    start: number;
    min: number;
    max: number;
  } | null>(null);
  const [regionDraft, setRegionDraft] = useState<{
    name: string;
    min: number;
    max: number;
  } | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) =>
      setSize({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      }),
    );
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    navigation.reset();
    setHover(null);
  }, [
    pattern.unit,
    onAutoRange ? null : pattern.x[0],
    onAutoRange ? null : pattern.x.at(-1),
    log,
    sqrt,
  ]);
  const right = 32,
    top = 18,
    bottom = 52;
  const w = Math.max(1, size.width - left - right),
    h = Math.max(1, size.height - top - bottom);
  const visibleCurves = showPattern ? [pattern, ...curves] : curves;
  const plottedX = visibleCurves.flatMap((curve) => curve.x);
  const [fitXMin, fitXMax] = plottedX.length ? extent(plottedX) : [0, 1];
  const transform = (y: number) =>
    log ? Math.log10(Math.max(1e-6, y)) : sqrt ? Math.sqrt(Math.max(0, y)) : y;
  const plottedY = visibleCurves.flatMap((curve) => curve.y);
  const visible = plottedY.filter(
    (y): y is number => y !== null && Number.isFinite(y) && (!log || y > 0),
  );
  const [fitYMin, fitYMax] = visible.length
    ? paddedExtent(visible.map(transform))
    : [0, 1];
  const navigation = usePlotNavigation(
    {
      xMin: fitXMin,
      xMax: Math.max(fitXMin + 1e-12, fitXMax),
      yMin: fitYMin,
      yMax: fitYMax,
    },
    { left, top, width: w, height: h },
    false,
    zoomMode,
    (xMin, xMax) => {
      const plottedPoints = visibleCurves.flatMap((curve) =>
        curve.x.map((x, i) => ({ x, y: curve.y[i] })),
      );
      const values = plottedPoints
        .filter(
          (point): point is { x: number; y: number } =>
            point.y !== null &&
            Number.isFinite(point.y) &&
            (!log || point.y > 0) &&
            point.x >= xMin &&
            point.x <= xMax,
        )
        .map((point) => point.y);

      if (!values.length) return [fitYMin, fitYMax];
      return paddedExtent(values.map(transform));
    },
  );
  useEffect(() => {
    if (autoRange) navigation.reset();
    else if (onAutoRange) navigation.hold();
  }, [pattern, autoRange, showPattern]);
  usePlotWheel(canvas, (event) => {
    onAutoRange?.(false);
    navigation.onWheel(event);
  });
  const { xMin: xmin, xMax: xmax, yMin: ymin, yMax: ymax } = navigation.view;
  const yspan = ymax - ymin;
  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!context || !canvas.current) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.current.width = Math.round(size.width * dpr);
    canvas.current.height = Math.round(size.height * dpr);
    context.scale(dpr, dpr);
    // Resizing clears the canvas; transparent margins reveal the workspace surface.
    context.font = "13px ui-monospace, SFMono-Regular, monospace";
    const intervalsY = Math.max(1, Math.floor(h / 48));
    const inverse = (v: number) => Math.max(0, v) ** 2;
    const yAxis = log
      ? { ticks: logTicks(ymin, ymax, intervalsY), annotation: null }
      : linearAxisTicks(
          sqrt ? inverse(ymin) : ymin,
          sqrt ? inverse(ymax) : ymax,
          intervalsY,
        );
    const yTicks = sqrt
      ? yAxis.ticks.map((tick) => ({
          ...tick,
          value: transform(tick.value),
        }))
      : yAxis.ticks;
    // Keep a separate gutter for the rotated title, regardless of intensity magnitude.
    const tickWidth = Math.max(
      0,
      ...yTicks.map((tick) => context.measureText(tick.label).width),
    );
    setLeft(Math.max(64, Math.ceil(tickWidth) + 44));
    let intervals = Math.max(1, Math.floor(w / 80));
    let xTicks = linearTicks(xmin, xmax, intervals);
    while (intervals > 1) {
      const widest = Math.max(
        0,
        ...xTicks.map((tick) => context.measureText(tick.label).width),
      );
      const spacing =
        xTicks.length > 1
          ? ((xTicks[1].value - xTicks[0].value) / (xmax - xmin)) * w
          : w;
      if (spacing >= widest + 18) break;
      xTicks = linearTicks(xmin, xmax, --intervals);
    }
    context.textBaseline = "middle";
    for (const tick of yTicks) {
      const y = top + h - ((tick.value - ymin) / yspan) * h;
      context.strokeStyle = "#222c36";
      context.beginPath();
      context.moveTo(left, y);
      context.lineTo(size.width - right, y);
      context.stroke();
      context.fillStyle = "#7e8994";
      context.textAlign = "right";
      context.fillText(tick.label, left - 10, y);
      context.strokeStyle = "#65717d";
      context.beginPath();
      context.moveTo(left - 4, y);
      context.lineTo(left, y);
      context.stroke();
    }
    for (const tick of xTicks) {
      const x = left + ((tick.value - xmin) / (xmax - xmin)) * w;
      context.strokeStyle = "#222c36";
      context.beginPath();
      context.moveTo(x, top);
      context.lineTo(x, top + h);
      context.stroke();
      context.strokeStyle = "#65717d";
      context.beginPath();
      context.moveTo(x, top + h);
      context.lineTo(x, top + h + 4);
      context.stroke();
      context.fillStyle = "#7e8994";
      context.textAlign = "center";
      const halfLabel = context.measureText(tick.label).width / 2;
      context.fillText(
        tick.label,
        Math.max(halfLabel + 6, Math.min(size.width - halfLabel - 6, x)),
        top + h + 18,
      );
    }
    context.strokeStyle = "#65717d";
    context.beginPath();
    context.moveTo(left, top);
    context.lineTo(left, top + h);
    context.lineTo(left + w, top + h);
    context.stroke();
    context.textBaseline = "alphabetic";
    if (yAxis.annotation) {
      context.textAlign = "left";
      context.fillStyle = "#7e8994";
      context.fillText(yAxis.annotation, left, top - 6);
    }
    context.save();
    context.beginPath();
    context.rect(left, top, w, h);
    context.clip();
    for (const region of regions) {
      const current = regionDraft?.name === region.name ? regionDraft : region;
      const x0 = left + ((current.min - xmin) / (xmax - xmin)) * w;
      const x1 = left + ((current.max - xmin) / (xmax - xmin)) * w;
      context.fillStyle = region.color + (region.active ? "28" : "12");
      context.fillRect(x0, top, x1 - x0, h);
      context.strokeStyle = region.color;
      context.lineWidth = region.active ? 2 : 1;
      context.strokeRect(x0, top, x1 - x0, h);
      context.fillStyle = region.color;
      context.textAlign = "left";
      context.fillText(region.name, x0 + 5, top + 14);
    }
    const drawCurve = (
      curve: { x: number[]; y: (number | null)[] },
      color: string,
      width: number,
    ) => {
      context.strokeStyle = color;
      context.fillStyle = color;
      context.lineWidth = width;
      const pixelWidth = width > 2 ? Math.round(width) : 1;
      context.beginPath();
      let previous: [number, number] | null = null;
      curve.x.forEach((x, i) => {
        const y = curve.y[i];
        if (y == null || !Number.isFinite(y) || (log && y <= 0)) {
          previous = null;
          return;
        }
        const point: [number, number] = [
          left + ((x - xmin) / (xmax - xmin)) * w,
          top + h - ((transform(y) - ymin) / yspan) * h,
        ];
        if (antialias) {
          if (previous) context.lineTo(...point);
          else context.moveTo(...point);
        } else if (previous) {
          // Clip before stepping to keep deeply zoomed, off-screen segments bounded.
          const dx = point[0] - previous[0],
            dy = point[1] - previous[1];
          let start = 0,
            end = 1;
          for (const [origin, delta, low, high] of [
            [previous[0], dx, left, left + w],
            [previous[1], dy, top, top + h],
          ]) {
            if (delta === 0) {
              if (origin < low || origin > high) end = -1;
            } else {
              const t0 = (low - origin) / delta,
                t1 = (high - origin) / delta;
              start = Math.max(start, Math.min(t0, t1));
              end = Math.min(end, Math.max(t0, t1));
            }
          }
          if (end >= start) {
            const steps = Math.max(
              1,
              Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)) * (end - start)),
            );
            for (let j = 0; j <= steps; j++) {
              const t = start + ((end - start) * j) / steps;
              context.fillRect(
                Math.floor(previous[0] + dx * t - (pixelWidth - 1) / 2),
                Math.floor(previous[1] + dy * t - (pixelWidth - 1) / 2),
                pixelWidth,
                pixelWidth,
              );
            }
          }
        }
        previous = point;
      });
      if (antialias) context.stroke();
    };
    if (showPattern && !emphasizePattern) drawCurve(pattern, patternColor, 1.4);
    // Measured curves and background inspection share the same axes and drawing mode.
    // Draw the selected overlay last so it remains identifiable where curves overlap.
    for (const curve of curves.filter((curve) => !curve.selected))
      drawCurve(curve, curve.color, 1.2);
    for (const curve of curves.filter((curve) => curve.selected))
      drawCurve(curve, curve.color, 2.4);
    if (showPattern && emphasizePattern) drawCurve(pattern, patternColor, 2.4);
    const largestReference = Math.max(
      1,
      extent(referenceLines.map((line) => line.intensity))[1],
    );
    for (const line of referenceLines) {
      const x = left + ((line.x - xmin) / (xmax - xmin)) * w;
      if (x < left || x > left + w) continue;
      context.strokeStyle = line.color;
      context.lineWidth = 1.3;
      context.beginPath();
      context.moveTo(x, top + h);
      context.lineTo(
        x,
        top + h - h * 0.3 * Math.max(0.05, line.intensity / largestReference),
      );
      context.stroke();
    }
    for (const reference of calibrantLines) {
      const x = left + ((reference.x - xmin) / (xmax - xmin)) * w;
      if (x < left || x > left + w) continue;
      const active = reference.ring === activeRing;
      context.strokeStyle = active ? "#ff4040d9" : "#ff4040b3";
      context.lineWidth = active ? 2.2 : 1;
      context.beginPath();
      context.moveTo(x, top);
      context.lineTo(x, top + h);
      context.stroke();
      if (showNumbers) {
        context.fillStyle = "#ff4040";
        context.fillText(String(reference.ring), x + 4, top + 14);
      }
    }
    if (linkedPosition !== undefined) {
      const x = left + ((linkedPosition - xmin) / (xmax - xmin)) * w;
      context.strokeStyle = "#8af0c4";
      context.lineWidth = 1.5;
      context.beginPath();
      context.moveTo(x, top);
      context.lineTo(x, top + h);
      context.stroke();
    }
    if (navigation.selection) {
      const { start, end } = navigation.selection;
      context.fillStyle = "#ff950020";
      context.strokeStyle = "#ff9500";
      const x = Math.min(start.x, end.x),
        y = Math.min(start.y, end.y);
      const width = Math.abs(end.x - start.x),
        height = Math.abs(end.y - start.y);
      context.fillRect(x, y, width, height);
      context.strokeRect(x, y, width, height);
    }
    if (hover !== null) {
      context.setLineDash([3, 4]);
      context.strokeStyle = "#7a8c9c";
      context.beginPath();
      context.moveTo(hover, top);
      context.lineTo(hover, top + h);
      context.stroke();
    }
    context.restore();
    context.fillStyle = "#929ca7";
    context.textAlign = "center";
    context.fillText(unitLabel(pattern.unit), left + w / 2, size.height - 8);
    context.save();
    context.translate(16, top + h / 2);
    context.rotate(-Math.PI / 2);
    context.textBaseline = "middle";
    context.fillText("Intensity (a.u.)", 0, 0);
    context.restore();
  }, [
    pattern,
    showPattern,
    emphasizePattern,
    patternColor,
    log,
    sqrt,
    antialias,
    size,
    hover,
    navigation.view,
    navigation.selection,
    linkedPosition,
    activeRing,
    calibrantLines,
    showNumbers,
    curves,
    referenceLines,
    regions,
    regionDraft,
    left,
  ]);
  const xvalue =
    hover === null ? null : xmin + ((hover - left) / w) * (xmax - xmin);
  const nearest =
    xvalue === null
      ? -1
      : pattern.x.reduce(
          (best, x, i) =>
            Math.abs(x - xvalue) < Math.abs(pattern.x[best] - xvalue)
              ? i
              : best,
          0,
        );
  useEffect(() => {
    onHover?.(
      nearest >= 0
        ? {
            x: pattern.x[nearest],
            y: pattern.y[nearest],
            unit: pattern.unit,
            hint: hoverHint,
          }
        : null,
    );
  }, [nearest, pattern, onHover, hoverHint]);
  return (
    <div ref={container} className="pattern-container">
      <canvas
        ref={canvas}
        data-testid="pattern-canvas"
        aria-label={`Integrated diffraction pattern; left-drag ${zoomMode} zoom, right-drag pan, right-click zoom out`}
        style={{ width: "100%", height: "100%" }}
        data-intensity-scale={log ? "log" : sqrt ? "sqrt" : "linear"}
        data-antialias={antialias}
        data-auto-range={autoRange}
        data-original-visible={showPattern}
        data-curve-count={curves.length}
        data-reference-count={referenceLines.length}
        data-linked-position={linkedPosition}
        data-active-ring={activeRing}
        data-zoom-mode={zoomMode}
        data-plot-left={left}
        data-plot-top={top}
        data-plot-width={w}
        data-plot-height={h}
        data-view-x-min={xmin}
        data-view-x-max={xmax}
        data-view-y-min={ymin}
        data-view-y-max={ymax}
        onContextMenu={(e) => e.preventDefault()}
        onAuxClick={(e) => e.preventDefault()}
        onPointerDown={(e) => {
          const point = navigation.screen(e);
          if (
            editRegions &&
            e.button === 0 &&
            !e.ctrlKey &&
            onRegionChange &&
            point.x >= left &&
            point.x <= left + w &&
            point.y >= top &&
            point.y <= top + h
          ) {
            const x = navigation.data(point).x;
            const tolerance = ((xmax - xmin) * 9) / w;
            const region = [...regions]
              .sort((a, b) => Number(!!b.active) - Number(!!a.active))
              .find((r) => x >= r.min - tolerance && x <= r.max + tolerance);
            if (region) {
              regionDrag.current = {
                name: region.name,
                start: x,
                min: region.min,
                max: region.max,
                mode:
                  Math.abs(x - region.min) < tolerance
                    ? "min"
                    : Math.abs(x - region.max) < tolerance
                      ? "max"
                      : "move",
              };
              e.currentTarget.setPointerCapture(e.pointerId);
              return;
            }
          }
          navigation.onPointerDown(e, true, zoomMode === "rectangle");
        }}
        onPointerMove={(e) => {
          const drag = regionDrag.current;
          if (drag) {
            const dx = navigation.data(navigation.screen(e)).x - drag.start;
            const min = drag.min + (drag.mode === "max" ? 0 : dx);
            const max = drag.max + (drag.mode === "min" ? 0 : dx);
            if (min < max) setRegionDraft({ name: drag.name, min, max });
            return;
          }
          const x = Math.max(
            left,
            Math.min(size.width - right, navigation.screen(e).x),
          );
          setHover(x);
          navigation.onPointerMove(e);
        }}
        onPointerUp={(e) => {
          if (regionDrag.current) {
            if (regionDraft)
              onRegionChange?.(
                regionDraft.name,
                regionDraft.min,
                regionDraft.max,
              );
            regionDrag.current = null;
            setRegionDraft(null);
            if (e.currentTarget.hasPointerCapture(e.pointerId))
              e.currentTarget.releasePointerCapture(e.pointerId);
            return;
          }
          const result = navigation.onPointerUp(e);
          if (result === "zoom" || result === "pan" || result === "unzoom")
            onAutoRange?.(false);
          if (result === "click")
            onPick?.(navigation.data(navigation.screen(e)).x);
        }}
        onPointerCancel={(e) => {
          regionDrag.current = null;
          setRegionDraft(null);
          navigation.onPointerCancel(e);
        }}
        onPointerLeave={() => setHover(null)}
      />
      {onZoomMode && (
        <PlotZoomControls
          mode={zoomMode}
          onChange={onZoomMode}
          left={left}
          bottom={bottom}
          label="Pattern"
        />
      )}
      {overlayLegend && (
        <OverlayPlotLegend
          entries={overlayLegend}
          left={left + w - 10}
          top={top + 5}
          width={w * 0.6}
          height={h * 0.5}
        />
      )}
    </div>
  );
}

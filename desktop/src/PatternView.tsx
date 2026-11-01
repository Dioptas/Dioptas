import { useEffect, useRef, useState } from "react";
import type { Pattern } from "./types";
import { number, unitLabel } from "./types";
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
  log,
  zoomMode = "horizontal",
  onPick,
  linkedPosition,
  calibrantLines = [],
  showNumbers = false,
  curves = [],
  referenceLines = [],
  regions = EMPTY_REGIONS,
  editRegions = false,
  onRegionChange,
}: {
  pattern: Pattern;
  log: boolean;
  zoomMode?: ZoomMode;
  onPick?: (x: number) => void;
  linkedPosition?: number;
  calibrantLines?: { x: number; ring: number }[];
  showNumbers?: boolean;
  curves?: NonNullable<Pattern["curves"]>;
  referenceLines?: NonNullable<Pattern["phaseLines"]>;
  regions?: PatternRegion[];
  editRegions?: boolean;
  onRegionChange?: (name: string, min: number, max: number) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    container = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 900, height: 230 });
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
  }, [pattern.unit, pattern.x[0], pattern.x.at(-1), log]);
  const left = 76,
    right = 24,
    top = 18,
    bottom = 44;
  const w = size.width - left - right,
    h = size.height - top - bottom;
  const [fitXMin, fitXMax] = extent([
    ...pattern.x,
    ...curves.flatMap((curve) => curve.x),
  ]);
  const transform = (y: number) => (log ? Math.log10(Math.max(1e-6, y)) : y);
  const plottedY = [...pattern.y, ...curves.flatMap((curve) => curve.y)];
  const visible = plottedY.filter(
    (y): y is number => y !== null && Number.isFinite(y) && (!log || y > 0),
  );
  const fitYMin = visible.length
    ? log
      ? extent(visible.map(transform))[0]
      : Math.min(0, extent(visible)[0])
    : 0;
  const fitYMax = visible.length ? extent(visible.map(transform))[1] : 1;
  const fitYSpan = Math.max(1e-6, fitYMax - fitYMin) * 1.08;
  const navigation = usePlotNavigation(
    {
      xMin: fitXMin,
      xMax: Math.max(fitXMin + 1e-12, fitXMax),
      yMin: fitYMin,
      yMax: fitYMin + fitYSpan,
    },
    { left, top, width: w, height: h },
    false,
    zoomMode,
    (xMin, xMax) => {
      const plottedPoints = [pattern, ...curves].flatMap((curve) =>
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

      if (!values.length) return [fitYMin, fitYMin + fitYSpan];
      const lower = log
        ? extent(values.map(transform))[0]
        : Math.min(0, extent(values)[0]);
      const upper = extent(values.map(transform))[1];
      return [lower, lower + Math.max(1e-6, upper - lower) * 1.08];
    },
  );
  usePlotWheel(canvas, navigation.onWheel);
  const { xMin: xmin, xMax: xmax, yMin: ymin, yMax: ymax } = navigation.view;
  const yspan = ymax - ymin;
  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!context || !canvas.current) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.current.width = Math.round(size.width * dpr);
    canvas.current.height = Math.round(size.height * dpr);
    context.scale(dpr, dpr);
    context.fillStyle = "#10151b";
    context.fillRect(0, 0, size.width, size.height);
    context.font = "13px ui-monospace, SFMono-Regular, monospace";
    for (let i = 0; i <= 4; i++) {
      const y = top + (h * i) / 4,
        value = ymin + yspan * (1 - i / 4);
      context.strokeStyle = "#222c36";
      context.beginPath();
      context.moveTo(left, y);
      context.lineTo(size.width - right, y);
      context.stroke();
      context.fillStyle = "#7e8994";
      context.textAlign = "right";
      context.fillText(number(log ? 10 ** value : value, 1), left - 10, y + 3);
      const x = left + (w * i) / 4;
      context.textAlign = "center";
      context.fillText(
        number(xmin + ((xmax - xmin) * i) / 4),
        x,
        size.height - 22,
      );
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
    context.strokeStyle = "#efba77";
    context.lineWidth = 1.4;
    context.beginPath();
    let started = false;
    pattern.x.forEach((x, i) => {
      const y = pattern.y[i];
      if (y === null || !Number.isFinite(y) || (log && y <= 0)) {
        started = false;
        return;
      }
      const px = left + ((x - xmin) / (xmax - xmin)) * w;
      const py = top + h - ((transform(y) - ymin) / yspan) * h;
      if (started) context.lineTo(px, py);
      else context.moveTo(px, py);
      started = true;
    });
    context.stroke();
    // Models own measured-curve scaling and reference coordinates. All use
    // the same plot axes, clipping and navigation as the primary pattern.
    for (const curve of curves) {
      context.strokeStyle = curve.color;
      context.lineWidth = 1.2;
      context.beginPath();
      let drawing = false;
      curve.x.forEach((x, i) => {
        const y = curve.y[i];
        if (y == null || !Number.isFinite(y) || (log && y <= 0)) {
          drawing = false;
          return;
        }
        const px = left + ((x - xmin) / (xmax - xmin)) * w;
        const py = top + h - ((transform(y) - ymin) / yspan) * h;
        if (drawing) context.lineTo(px, py);
        else context.moveTo(px, py);
        drawing = true;
      });
      context.stroke();
    }
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
      context.strokeStyle = "#7bb5a877";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(x, top);
      context.lineTo(x, top + h);
      context.stroke();
      if (showNumbers) {
        context.fillStyle = "#a2c7ba";
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
      context.fillStyle = "#efba7720";
      context.strokeStyle = "#efba77";
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
    context.fillText(unitLabel(pattern.unit), left + w / 2, size.height - 5);
    context.save();
    context.translate(12, top + h / 2);
    context.rotate(-Math.PI / 2);
    context.fillText("Intensity (a.u.)", 0, 0);
    context.restore();
  }, [
    pattern,
    log,
    size,
    hover,
    navigation.view,
    navigation.selection,
    linkedPosition,
    calibrantLines,
    showNumbers,
    curves,
    referenceLines,
    regions,
    regionDraft,
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
  return (
    <div ref={container} className="pattern-container">
      <canvas
        ref={canvas}
        data-testid="pattern-canvas"
        aria-label={`Integrated diffraction pattern; left-drag ${zoomMode} zoom, right-drag pan, right-click zoom out`}
        style={{ width: "100%", height: "100%" }}
        data-curve-count={curves.length}
        data-reference-count={referenceLines.length}
        data-linked-position={linkedPosition}
        data-zoom-mode={zoomMode}
        data-view-x-min={xmin}
        data-view-x-max={xmax}
        data-view-y-min={ymin}
        data-view-y-max={ymax}
        onContextMenu={(e) => e.preventDefault()}
        onAuxClick={(e) => e.preventDefault()}
        onPointerDown={(e) => {
          if (editRegions && e.button === 0 && !e.ctrlKey && onRegionChange) {
            const x = navigation.data(navigation.screen(e)).x;
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
          navigation.onPointerDown(e);
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
          if (navigation.onPointerUp(e) === "click")
            onPick?.(navigation.data(navigation.screen(e)).x);
        }}
        onPointerCancel={(e) => {
          regionDrag.current = null;
          setRegionDraft(null);
          navigation.onPointerCancel(e);
        }}
        onPointerLeave={() => setHover(null)}
      />
      {nearest >= 0 && (
        <div className="plot-readout">
          {unitLabel(pattern.unit)} <b>{number(pattern.x[nearest], 4)}</b>
          <span>
            I <b>{number(pattern.y[nearest] ?? 0)}</b>
          </span>
        </div>
      )}
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import type { Pattern } from "./types";
import { number, unitLabel } from "./types";
import {
  usePlotNavigation,
  usePlotWheel,
  type ZoomMode,
} from "./usePlotNavigation";

export function PatternView({
  pattern,
  log,
  zoomMode = "horizontal",
  onPick,
  linkedPosition,
  calibrantLines = [],
  showNumbers = false,
}: {
  pattern: Pattern;
  log: boolean;
  zoomMode?: ZoomMode;
  onPick?: (x: number) => void;
  linkedPosition?: number;
  calibrantLines?: { x: number; ring: number }[];
  showNumbers?: boolean;
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    container = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 900, height: 230 });
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
  const fitXMin = Math.min(pattern.x[0], pattern.x.at(-1)!);
  const fitXMax = Math.max(pattern.x[0], pattern.x.at(-1)!);
  const transform = (y: number) => (log ? Math.log10(Math.max(1e-6, y)) : y);
  const visible = pattern.y.filter(
    (y): y is number => y !== null && Number.isFinite(y) && (!log || y > 0),
  );
  const fitYMin = visible.length
    ? log
      ? Math.min(...visible.map(transform))
      : Math.min(0, ...visible)
    : 0;
  const fitYMax = visible.length ? Math.max(...visible.map(transform)) : 1;
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
      const values = pattern.y.filter(
        (y, i): y is number =>
          y !== null &&
          Number.isFinite(y) &&
          (!log || y > 0) &&
          pattern.x[i] >= xMin &&
          pattern.x[i] <= xMax,
      );
      if (!values.length) return [fitYMin, fitYMin + fitYSpan];
      const lower = log
        ? Math.min(...values.map(transform))
        : Math.min(0, ...values);
      const upper = Math.max(...values.map(transform));
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
        data-linked-position={linkedPosition}
        data-zoom-mode={zoomMode}
        data-view-x-min={xmin}
        data-view-x-max={xmax}
        data-view-y-min={ymin}
        data-view-y-max={ymax}
        onContextMenu={(e) => e.preventDefault()}
        onAuxClick={(e) => e.preventDefault()}
        onPointerDown={(e) => {
          navigation.onPointerDown(e);
        }}
        onPointerMove={(e) => {
          const x = Math.max(
            left,
            Math.min(size.width - right, navigation.screen(e).x),
          );
          setHover(x);
          navigation.onPointerMove(e);
        }}
        onPointerUp={(e) => {
          if (navigation.onPointerUp(e) === "click")
            onPick?.(navigation.data(navigation.screen(e)).x);
        }}
        onPointerCancel={navigation.onPointerCancel}
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

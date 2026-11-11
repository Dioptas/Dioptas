import { useCakeAxisGesture } from "./CakeProfileWorkspace";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  usePlotNavigation,
  usePlotWheel,
  type PlotRange,
} from "./usePlotNavigation";
import { usePlotTypography } from "./usePlotTypography";
import { linearAxisTicks } from "./plotTicks";
import { POSITION_LINE_COLOR } from "./plotColors";
import { RANGE_SELECTION_COLOR } from "./drawRangeSelection";
import type { Cake, CakeProfile } from "./types";
import type { PlotViewport } from "./plotViewport";

/** The profile uses exactly the cake's source row coordinates, not a new axis. */
export function CakeProfileView({
  profile,
  emptyMessage,
  cake,
  cakeView,
  onAzimuthRange,
  selectedAzimuth,
  context,
  onInspect,
  onHover,
}: {
  profile: CakeProfile | null;
  emptyMessage?: string;
  cake: Cake | null;
  cakeView: PlotRange;
  onAzimuthRange: (range: [number, number]) => void;
  selectedAzimuth?: number | null;
  context: string;
  onInspect: (azimuth: number) => void;
  onHover: (
    point: {
      azimuth: number;
      intensity: number | null;
      resolution: number;
    } | null,
  ) => void;
}) {
  const container = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 160, height: 400 });
  const typography = usePlotTypography(container);
  useLayoutEffect(() => {
    const node = container.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) =>
      setSize({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      }),
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  // Match RasterView's cake plot insets. Both canvases occupy the same grid row.
  const [axisWidth, setAxisWidth] = useState(60);
  const left = axisWidth,
    right = 6,
    top = 20,
    bottom = 44 * typography.scale;
  const width = Math.max(1, size.width - left - right),
    height = Math.max(1, size.height - top - bottom);
  const rows = cake?.fullHeight ?? profile?.y.length ?? 1;
  const extent = useMemo(() => {
    let min = Infinity,
      max = -Infinity;
    profile?.y.forEach((value, index) => {
      if (
        value != null &&
        value !== 0 &&
        Number.isFinite(value) &&
        index + 0.5 >= cakeView.yMin &&
        index + 0.5 <= cakeView.yMax
      ) {
        min = Math.min(min, value);
        max = Math.max(max, value);
      }
    });
    if (!Number.isFinite(min)) return [0, 1];
    const pad = Math.max((max - min) * 0.05, Math.abs(min) * 1e-6, 1e-6);
    return [min - pad, max + pad];
  }, [profile, cakeView.yMin, cakeView.yMax]);
  const intensityView = useRef<{ key: string; range: PlotRange | null }>({
    key: context,
    range: null,
  });
  if (intensityView.current.key !== context)
    intensityView.current = { key: context, range: null };
  const [, render] = useState(0);
  const viewport: PlotViewport = {
    key: context,
    read: () => ({
      xMin: intensityView.current.range?.xMin ?? extent[0],
      xMax: intensityView.current.range?.xMax ?? extent[1],
      yMin: cakeView.yMin,
      yMax: cakeView.yMax,
    }),
    write: (range) => {
      intensityView.current.range = range;
      onAzimuthRange(range ? [range.yMin, range.yMax] : [0, rows]);
      render((v) => v + 1);
    },
  };
  const navigation = usePlotNavigation(
    { xMin: extent[0], xMax: extent[1], yMin: 0, yMax: rows },
    { left, top, width, height },
    false,
    "rectangle",
    undefined,
    viewport,
  );
  const axisGesture = useCakeAxisGesture("profile", canvas, navigation);
  usePlotWheel(canvas, navigation.onWheel);
  const view = navigation.view;
  const yPixel = (row: number) =>
    top + ((view.yMax - row) / (view.yMax - view.yMin)) * height;
  const xPixel = (value: number) =>
    left + ((value - view.xMin) / (view.xMax - view.xMin)) * width;
  const azimuthAt = (row: number) => {
    if (!cake) return NaN;
    return (
      cake.azimuthRange[0] +
      (row / rows) * (cake.azimuthRange[1] - cake.azimuthRange[0])
    );
  };
  const pointAt = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const p = navigation.screen(event);
    if (p.x < left || p.x > left + width || p.y < top || p.y > top + height)
      return null;
    const row = navigation.data(p).y;
    return {
      azimuth: azimuthAt(row),
      intensity: profile?.y[Math.floor(row)] ?? null,
      resolution: cake
        ? ((Math.abs(cake.azimuthRange[1] - cake.azimuthRange[0]) / rows) *
            (view.yMax - view.yMin)) /
          height
        : 0.01,
    };
  };
  useLayoutEffect(() => {
    const node = canvas.current;
    if (!node) return;
    const dpr = window.devicePixelRatio || 1;
    node.width = Math.max(1, Math.round(size.width * dpr));
    node.height = Math.max(1, Math.round(size.height * dpr));
    const c = node.getContext("2d");
    if (!c) return;
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, size.width, size.height);
    c.font = typography.mono;
    c.strokeStyle = "#35404a";
    c.lineWidth = 1;
    c.beginPath();
    c.moveTo(left, top + height);
    c.lineTo(left + width, top + height);
    c.stroke();
    const ticks = linearAxisTicks(
      view.xMin,
      view.xMax,
      Math.max(1, Math.floor(width / 70)),
    );
    c.fillStyle = typography.muted;
    c.textAlign = "center";
    for (const tick of ticks.ticks) {
      const x = xPixel(tick.value);
      c.beginPath();
      c.moveTo(x, top + height);
      c.lineTo(x, top + height + 4);
      c.stroke();
      const half = c.measureText(tick.label).width / 2;
      c.fillText(
        tick.label,
        Math.max(half + 2, Math.min(size.width - half - 2, x)),
        size.height - 18,
      );
    }
    if (ticks.annotation) {
      c.textAlign = "left";
      c.fillText(ticks.annotation, left, top - 6);
    }
    // One far-left azimuth axis labels both the row projection and the cake.
    const yAxis = linearAxisTicks(
      azimuthAt(view.yMin),
      azimuthAt(view.yMax),
      Math.max(1, Math.floor(height / (48 * typography.scale))),
    );
    const tickWidth = Math.max(
      0,
      ...yAxis.ticks.map((t) => c.measureText(t.label).width),
    );
    setAxisWidth(Math.max(60, Math.ceil(tickWidth) + 36));
    c.textAlign = "right";
    for (const tick of yAxis.ticks) {
      const [low, high] = cake?.azimuthRange ?? [0, 1];
      const y = yPixel(((tick.value - low) / (high - low)) * rows);
      c.beginPath();
      c.moveTo(left - 4, y);
      c.lineTo(left, y);
      c.stroke();
      c.fillText(tick.label, left - 8, y + 3);
    }
    if (yAxis.annotation) {
      c.textAlign = "left";
      c.fillText(yAxis.annotation, left, top - 6);
    }
    c.save();
    c.translate(11, top + height / 2);
    c.rotate(-Math.PI / 2);
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.fillText(height < 120 ? "χ (°)" : "Azimuth (°)", 0, 0);
    c.restore();
    c.textAlign = "center";
    c.font = typography.text;
    c.fillText("Intensity", left + width / 2, size.height - 3);
    c.save();
    c.beginPath();
    c.rect(left, top, width, height);
    c.clip();
    if (emptyMessage) {
      c.font = typography.text;
      c.fillStyle = typography.muted;
      c.textAlign = "center";
      c.textBaseline = "middle";
      c.fillText(emptyMessage, left + width / 2, top + height / 2);
    }
    c.strokeStyle = "#ffffff";
    c.lineWidth = 1.5;
    c.beginPath();
    let drawing = false;
    profile?.y.forEach((value, index) => {
      if (value == null || value === 0 || !Number.isFinite(value)) {
        drawing = false;
        return;
      }
      const x = xPixel(value),
        y = yPixel(index + 0.5);
      if (drawing) c.lineTo(x, y);
      else c.moveTo(x, y);
      drawing = true;
    });
    c.stroke();
    if (selectedAzimuth != null && cake) {
      const [low, high] = cake.azimuthRange;
      const period = rows > 1 ? ((high - low) * rows) / (rows - 1) : 0;
      const a =
        period >= 359
          ? low + ((((selectedAzimuth - low) % 360) + 360) % 360)
          : selectedAzimuth;
      const y = yPixel(((a - low) / (high - low)) * rows);
      c.strokeStyle = POSITION_LINE_COLOR;
      c.setLineDash([6, 3]);
      c.beginPath();
      c.moveTo(left, y);
      c.lineTo(left + width, y);
      c.stroke();
      c.setLineDash([]);
    }
    if (navigation.selection) {
      const { start, end } = navigation.selection;
      c.fillStyle = RANGE_SELECTION_COLOR + "22";
      c.strokeStyle = RANGE_SELECTION_COLOR;
      c.fillRect(start.x, start.y, end.x - start.x, end.y - start.y);
      c.strokeRect(start.x, start.y, end.x - start.x, end.y - start.y);
    }
    c.restore();
  }, [
    profile,
    emptyMessage,
    cake,
    selectedAzimuth,
    size,
    typography.size,
    typography.muted,
    view.xMin,
    view.xMax,
    view.yMin,
    view.yMax,
    axisWidth,
    navigation.selection,
  ]);
  useEffect(() => () => onHover(null), []);
  return (
    <div ref={container} className="cake-profile-view">
      <canvas
        ref={canvas}
        tabIndex={0}
        data-testid="cake-profile-canvas"
        aria-label="Azimuthal profile; intensity horizontally, shared cake azimuth vertically; left-drag zoom, right-drag pan, F fits"
        data-plot-left={left}
        data-plot-top={top}
        data-plot-width={width}
        data-plot-height={height}
        data-view-x-min={view.xMin}
        data-view-x-max={view.xMax}
        data-view-y-min={view.yMin}
        data-view-y-max={view.yMax}
        data-azimuth-min={cake ? azimuthAt(view.yMin) : undefined}
        data-azimuth-max={cake ? azimuthAt(view.yMax) : undefined}
        data-profile-row-count={profile?.y.length ?? 0}
        data-profile-shift-bins={profile?.shiftBins ?? 0}
        aria-description={emptyMessage}
        onKeyDown={navigation.onKeyDown}
        onContextMenu={(event) => event.preventDefault()}
        onPointerDown={(event) => {
          const point = navigation.screen(event);
          if (
            point.x < left &&
            point.y >= top &&
            point.y <= top + height &&
            axisGesture?.start(event)
          )
            return;
          navigation.onPointerDown(event);
        }}
        onPointerMove={(event) => {
          if (axisGesture?.move(event)) return;
          navigation.onPointerMove(event);
          onHover(pointAt(event));
        }}
        onPointerLeave={() => onHover(null)}
        onPointerCancel={(event) => {
          if (!axisGesture?.cancel(event)) navigation.onPointerCancel(event);
        }}
        onPointerUp={(event) => {
          if (axisGesture?.finish(event)) return;
          if (navigation.onPointerUp(event) === "click") {
            const point = pointAt(event);
            if (point) onInspect(point.azimuth);
          }
        }}
      />
    </div>
  );
}

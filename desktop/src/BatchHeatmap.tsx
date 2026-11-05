import { useEffect, useMemo, useRef, useState } from "react";
import type { BatchData } from "./batchDomain";
import { decodeRaster } from "./rasterTransfer";
import { unitLabel, number } from "./types";
import { linearTicks } from "./plotTicks";
import { rasterCanvas } from "./rasterCanvas";
import {
  usePlotNavigation,
  usePlotWheel,
  type ZoomMode,
} from "./usePlotNavigation";
import type { ReportPlot } from "./plotReadout";
import { PlotZoomControls } from "./PlotZoomControls";
import {
  drawRangeSelection,
  RANGE_SELECTION_COLOR,
} from "./drawRangeSelection";

/** Bin-space projection retains every sample, including a nonuniform d axis.
 * Labels interpolate the stored radial coordinates, never assume 2theta.
 */
export function BatchHeatmap({
  batch,
  viewport,
  zoomMode,
  onZoomMode,
  limits,
  log,
  sqrt = false,
  palette,
  ready,
  onSelect,
  reportPlot,
}: {
  batch: BatchData;
  viewport?: import("./plotViewport").PlotViewport;
  zoomMode: ZoomMode;
  onZoomMode: (mode: ZoomMode) => void;
  limits: [number, number];
  log: boolean;
  sqrt?: boolean;
  palette: string;
  ready: boolean;
  onSelect: (index: number) => void;
  reportPlot: ReportPlot;
}) {
  const host = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 600, height: 400 });
  const rows = batch.entries.length,
    cols = batch.x.length;
  const left = Math.max(36, String(Math.max(0, rows - 1)).length * 8 + 12);
  const bounds = {
    left,
    top: 12,
    width: Math.max(1, size.width - left - 18),
    height: Math.max(1, size.height - 58),
  };
  const nav = usePlotNavigation(
    { xMin: 0, xMax: cols, yMin: 0, yMax: rows },
    bounds,
    false,
    zoomMode,
    undefined,
    viewport,
  );
  const values = useMemo(() => decodeRaster(batch.raster), [batch.raster.data]);
  const coloredValues = useMemo(
    () =>
      sqrt
        ? Float32Array.from(values, (v) => Math.sqrt(Math.max(0, v)))
        : values,
    [values, sqrt],
  );
  const bitmap = useMemo(
    () =>
      rasterCanvas(
        batch.raster,
        coloredValues,
        undefined,
        null,
        ...(sqrt
          ? ([
              Math.sqrt(Math.max(0, limits[0])),
              Math.sqrt(Math.max(0, limits[1])),
            ] as [number, number])
          : limits),
        log,
        palette,
        0,
      ),
    [batch.raster, coloredValues, limits, log, sqrt, palette],
  );
  useEffect(() => {
    const observer = new ResizeObserver(([e]) =>
      setSize({ width: e.contentRect.width, height: e.contentRect.height }),
    );
    observer.observe(host.current!);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!viewport) nav.reset();
  }, [rows, cols]);
  usePlotWheel(canvas, nav.onWheel);
  const radial = (bin: number) => {
    const p = Math.max(0, Math.min(cols - 1, bin - 0.5)),
      i = Math.floor(p);
    return (
      batch.x[i] + (batch.x[Math.min(cols - 1, i + 1)] - batch.x[i]) * (p - i)
    );
  };
  useEffect(() => {
    const c = canvas.current!,
      dpr = window.devicePixelRatio || 1;
    c.width = Math.round(size.width * dpr);
    c.height = Math.round(size.height * dpr);
    const ctx = c.getContext("2d")!;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, size.width, size.height);
    const v = nav.view,
      sx = bounds.width / (v.xMax - v.xMin),
      sy = bounds.height / (v.yMax - v.yMin);
    const px = (x: number) => bounds.left + (x - v.xMin) * sx;
    const py = (y: number) => bounds.top + (v.yMax - y) * sy;
    ctx.save();
    ctx.beginPath();
    ctx.rect(bounds.left, bounds.top, bounds.width, bounds.height);
    ctx.clip();
    ctx.imageSmoothingEnabled = false;
    // Frame zero is at the bottom. Flip only the bitmap, keeping stored rows
    // and frame indices in acquisition order.
    ctx.save();
    ctx.translate(px(0), py(0));
    ctx.scale(sx, -sy);
    ctx.drawImage(bitmap, 0, 0, cols, rows);
    ctx.restore();
    const y = py(batch.selected + 0.5);
    ctx.strokeStyle = "#ff9500";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(px(0), y);
    ctx.lineTo(px(cols), y);
    ctx.stroke();
    ctx.fillStyle = "#ff9500";
    ctx.beginPath();
    ctx.moveTo(bounds.left, y - 5);
    ctx.lineTo(bounds.left + 7, y);
    ctx.lineTo(bounds.left, y + 5);
    ctx.fill();
    if (nav.selection) {
      ctx.lineWidth = 1.5;
      const { start, end } = nav.selection;
      const x = Math.min(start.x, end.x),
        y = Math.min(start.y, end.y),
        width = Math.abs(end.x - start.x),
        height = Math.abs(end.y - start.y);
      if (zoomMode === "horizontal") {
        drawRangeSelection(ctx, x, x + width, y, height, RANGE_SELECTION_COLOR);
      } else {
        ctx.fillStyle = RANGE_SELECTION_COLOR + "20";
        ctx.strokeStyle = RANGE_SELECTION_COLOR;
        ctx.fillRect(x, y, width, height);
        ctx.strokeRect(x, y, width, height);
      }
    }
    ctx.restore();
    ctx.strokeStyle = "#65717d";
    ctx.lineWidth = 1;
    ctx.strokeRect(bounds.left, bounds.top, bounds.width, bounds.height);
    ctx.font = `${host.current?.closest(".app")?.getAttribute("data-text-size") === "large" ? 14 : 13}px -apple-system, sans-serif`;
    ctx.fillStyle = "#7e8994";
    ctx.textAlign = "center";
    const a = radial(v.xMin),
      b = radial(v.xMax);
    const ticks = linearTicks(
      Math.min(a, b),
      Math.max(a, b),
      Math.max(2, Math.floor(bounds.width / 90)),
    );
    for (const tick of ticks) {
      const ascending = batch.x[cols - 1] > batch.x[0];
      let low = 0,
        high = cols - 1;
      while (high - low > 1) {
        const mid = (low + high) >>> 1;
        if (batch.x[mid] < tick.value === ascending) low = mid;
        else high = mid;
      }
      const fraction =
        (tick.value - batch.x[low]) / (batch.x[high] - batch.x[low]);
      const bin =
        cols === 1 ? 0.5 : low + Math.max(0, Math.min(1, fraction)) + 0.5;
      ctx.fillText(tick.label, px(bin), size.height - 26);
    }
    ctx.fillStyle = "#929ca7";
    ctx.fillText(
      unitLabel(batch.unit),
      bounds.left + bounds.width / 2,
      size.height - 6,
    );
    ctx.fillStyle = "#7e8994";
    ctx.textAlign = "right";
    const stride = Math.max(
      1,
      Math.ceil((v.yMax - v.yMin) / Math.max(1, bounds.height / 42)),
    );
    for (
      let i = Math.max(0, Math.floor(v.yMin));
      i < Math.min(rows, Math.ceil(v.yMax));
      i += stride
    ) {
      ctx.fillText(String(i), bounds.left - 9, py(i + 0.5) + 4);
    }
  }, [
    size,
    bitmap,
    nav.view,
    nav.selection,
    batch.selected,
    batch.unit,
    zoomMode,
  ]);
  const hit = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const p = nav.screen(event),
      d = nav.data(p);
    const index = Math.floor(d.y),
      bin = Math.floor(d.x);
    return p.x >= bounds.left &&
      p.x <= bounds.left + bounds.width &&
      p.y >= bounds.top &&
      p.y <= bounds.top + bounds.height &&
      index >= 0 &&
      index < rows &&
      bin >= 0 &&
      bin < cols
      ? { index, bin }
      : null;
  };
  return (
    <div ref={host} className="batch-heatmap">
      <canvas
        ref={canvas}
        data-testid="batch-heatmap"
        data-unit={batch.unit}
        data-intensity-scale={log ? "log" : sqrt ? "sqrt" : "linear"}
        data-zoom-mode={zoomMode}
        data-view-x-min={nav.view.xMin}
        data-view-x-max={nav.view.xMax}
        data-view-y-min={nav.view.yMin}
        data-view-y-max={nav.view.yMax}
        aria-label="Batch intensity overview"
        tabIndex={0}
        onContextMenu={(e) => e.preventDefault()}
        onPointerDown={(e) => {
          e.currentTarget.focus();
          nav.onPointerDown(e);
        }}
        onPointerMove={(e) => {
          nav.onPointerMove(e);
          const p = hit(e);
          reportPlot(
            "map",
            p
              ? {
                  text: `Frame ${p.index} · ${unitLabel(batch.unit)} ${number(batch.x[p.bin], 5)} · I ${number(values[p.index * cols + p.bin], 5)}`,
                  hint: `Click a row to select a pattern. Drag for ${zoomMode === "horizontal" ? "X-range" : "rectangle"} zoom; right drag to pan.`,
                }
              : null,
          );
        }}
        onPointerLeave={() => reportPlot("map", null)}
        onPointerUp={(e) => {
          const gesture = nav.onPointerUp(e),
            p = hit(e);
          if (gesture === "click" && p && ready) onSelect(p.index);
        }}
        onPointerCancel={nav.onPointerCancel}
        onKeyDown={(e) => {
          if (e.key.toLowerCase() === "f") {
            e.preventDefault();
            nav.reset();
          }
          if (
            ready &&
            ["ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)
          ) {
            e.preventDefault();
            onSelect(
              e.key === "Home"
                ? 0
                : e.key === "End"
                  ? rows - 1
                  : Math.max(
                      0,
                      Math.min(
                        rows - 1,
                        batch.selected + (e.key === "ArrowUp" ? 1 : -1),
                      ),
                    ),
            );
          }
        }}
      />
      <PlotZoomControls
        mode={zoomMode}
        onChange={onZoomMode}
        left={bounds.left}
        bottom={24}
        label="Batch"
        horizontalTitle="X-range zoom: keep the frame range"
      />
    </div>
  );
}

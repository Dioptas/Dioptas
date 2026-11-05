import { useEffect, useMemo, useRef, useState } from "react";
import type { BatchData } from "./batchDomain";
import { decodeRaster } from "./rasterTransfer";
import { unitLabel, number } from "./types";
import { linearTicks } from "./plotTicks";
import { rasterCanvas } from "./rasterCanvas";
import { usePlotNavigation, usePlotWheel } from "./usePlotNavigation";
import type { ReportPlot } from "./plotReadout";

/** Bin-space projection retains every sample, including a nonuniform d axis.
 * Labels interpolate the stored radial coordinates, never assume 2theta.
 */
export function BatchHeatmap({
  batch,
  limits,
  log,
  palette,
  ready,
  onSelect,
  reportPlot,
}: {
  batch: BatchData;
  limits: [number, number];
  log: boolean;
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
  const bounds = {
    left: 58,
    top: 12,
    width: Math.max(1, size.width - 76),
    height: Math.max(1, size.height - 58),
  };
  const nav = usePlotNavigation(
    { xMin: 0, xMax: cols, yMin: 0, yMax: rows },
    bounds,
  );
  const values = useMemo(() => decodeRaster(batch.raster), [batch.raster.data]);
  const bitmap = useMemo(
    () =>
      rasterCanvas(
        batch.raster,
        values,
        undefined,
        null,
        ...limits,
        log,
        palette,
        0,
      ),
    [batch.raster, values, limits, log, palette],
  );
  useEffect(() => {
    const observer = new ResizeObserver(([e]) =>
      setSize({ width: e.contentRect.width, height: e.contentRect.height }),
    );
    observer.observe(host.current!);
    return () => observer.disconnect();
  }, []);
  useEffect(() => nav.reset(), [rows, cols]);
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
    ctx.fillStyle = "#202226";
    ctx.fillRect(0, 0, size.width, size.height);
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
    // Row zero is the first file, at the top of the series.
    ctx.drawImage(bitmap, px(0), py(rows), cols * sx, rows * sy);
    const y = py(rows - batch.selected - 0.5);
    ctx.strokeStyle = "#ff9500";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(
      px(0),
      py(rows - batch.selected),
      cols * sx,
      Math.max(1, sy),
    );
    ctx.fillStyle = "#ff9500";
    ctx.beginPath();
    ctx.moveTo(bounds.left, y - 5);
    ctx.lineTo(bounds.left + 7, y);
    ctx.lineTo(bounds.left, y + 5);
    ctx.fill();
    if (nav.selection) {
      const { start, end } = nav.selection;
      ctx.fillStyle = "#ff950026";
      ctx.strokeStyle = "#ff9500";
      ctx.fillRect(start.x, start.y, end.x - start.x, end.y - start.y);
      ctx.strokeRect(start.x, start.y, end.x - start.x, end.y - start.y);
    }
    ctx.restore();
    ctx.strokeStyle = "#666a70";
    ctx.lineWidth = 1;
    ctx.strokeRect(bounds.left, bounds.top, bounds.width, bounds.height);
    ctx.font = `${host.current?.closest(".app")?.getAttribute("data-text-size") === "large" ? 14 : 13}px -apple-system, sans-serif`;
    ctx.fillStyle = "#c7c9cd";
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
    ctx.fillText(
      unitLabel(batch.unit),
      bounds.left + bounds.width / 2,
      size.height - 6,
    );
    ctx.textAlign = "right";
    const stride = Math.max(
      1,
      Math.ceil((v.yMax - v.yMin) / Math.max(1, bounds.height / 42)),
    );
    for (
      let i = Math.max(0, Math.floor(rows - v.yMax));
      i < Math.min(rows, Math.ceil(rows - v.yMin));
      i += stride
    ) {
      ctx.fillText(String(i + 1), bounds.left - 9, py(rows - i - 0.5) + 4);
    }
    ctx.save();
    ctx.translate(15, bounds.top + bounds.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText("Pattern", 0, 0);
    ctx.restore();
  }, [size, bitmap, nav.view, nav.selection, batch.selected, batch.unit]);
  const hit = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const p = nav.screen(event),
      d = nav.data(p);
    const index = rows - 1 - Math.floor(d.y),
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
                  text: `Pattern ${p.index + 1} · ${unitLabel(batch.unit)} ${number(batch.x[p.bin], 5)} · I ${number(values[p.index * cols + p.bin], 5)}`,
                  hint: "Click a row to select a pattern. Drag to zoom; right drag to pan.",
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
                        batch.selected + (e.key === "ArrowUp" ? -1 : 1),
                      ),
                    ),
            );
          }
        }}
      />
    </div>
  );
}

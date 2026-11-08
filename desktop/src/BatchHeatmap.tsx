import { Equal } from "lucide-react";
import { PlotToggle } from "./IntegrationPlotControls";
import { usePlotTypography } from "./usePlotTypography";
import { useEffect, useMemo, useRef, useState } from "react";
import type { BatchData } from "./batchDomain";
import { decodeRaster } from "./rasterTransfer";
import { unitLabel, type Pattern } from "./types";
import { batchNormalizationRegion } from "./batchDisplay";
import { scientificValue } from "./ScientificNumberInput";
import { radialFields, radialValues } from "./radialReadout";
import { intensityValue } from "./readoutNumbers";
import type { PatternPosition } from "./linkedPosition";
import { POSITION_LINE_COLOR } from "./plotColors";
import { batchRadialBin } from "./batchPlot";
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
  position,
  phaseLines,
  viewport,
  zoomMode,
  onZoomMode,
  limits,
  log,
  sqrt = false,
  palette,
  ready,
  onSelect,
  onNormalize,
  reportPlot,
}: {
  batch: BatchData;
  position?: PatternPosition;
  phaseLines?: Pattern["phaseLines"];
  viewport?: import("./plotViewport").PlotViewport;
  zoomMode: ZoomMode;
  onZoomMode: (mode: ZoomMode) => void;
  limits: [number, number];
  log: boolean;
  sqrt?: boolean;
  palette: string;
  ready: boolean;
  onSelect: (index: number, position?: PatternPosition) => void;
  reportPlot: ReportPlot;
  onNormalize: () => void;
}) {
  const host = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 600, height: 400 });
  const rows = batch.entries.length,
    cols = batch.x.length;
  const typography = usePlotTypography(host);
  const left = Math.max(
    28 * typography.scale,
    String(rows).length * 8 * typography.scale + 12,
  );
  const bounds = {
    left,
    top: 12,
    width: Math.max(1, size.width - left - 18),
    height: Math.max(1, size.height - 58 * typography.scale),
  };
  const nav = usePlotNavigation(
    { xMin: 0, xMax: cols, yMin: 0, yMax: rows },
    bounds,
    false,
    zoomMode,
    undefined,
    viewport,
  );
  const normalizationRegion = batchNormalizationRegion(batch);
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
    const maxima = new Map<number, number>();
    for (const line of phaseLines ?? [])
      maxima.set(
        line.phaseIndex ?? 0,
        Math.max(maxima.get(line.phaseIndex ?? 0) ?? 0, line.intensity),
      );
    for (const line of phaseLines ?? []) {
      const x = radialValues(line.x, "d_A", batch.wavelength ?? undefined)[
        batch.unit
      ];
      const bin = x == null ? null : batchRadialBin(x, batch.x);
      if (bin == null) continue;
      const maximum = maxima.get(line.phaseIndex ?? 0) ?? 0;
      const strength =
        maximum > 0 ? Math.max(0, Math.min(1, line.intensity / maximum)) : 0;
      ctx.strokeStyle = line.color;
      ctx.lineWidth = 1 + 3 * strength;
      ctx.globalAlpha = 0.3 + 0.4 * strength;
      ctx.beginPath();
      ctx.moveTo(px(bin), bounds.top);
      ctx.lineTo(px(bin), bounds.top + bounds.height);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    const clicked =
      position &&
      radialValues(position.x, position.unit, batch.wavelength ?? undefined)[
        batch.unit
      ];
    const clickedBin =
      clicked == null ? null : batchRadialBin(clicked, batch.x);
    if (clickedBin != null) {
      ctx.strokeStyle = POSITION_LINE_COLOR;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(px(clickedBin), bounds.top);
      ctx.lineTo(px(clickedBin), bounds.top + bounds.height);
      ctx.stroke();
    }
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
    ctx.font = typography.mono;
    ctx.fillStyle = typography.muted;
    ctx.textAlign = "center";
    const a = radial(v.xMin),
      b = radial(v.xMax);
    const ticks = linearTicks(
      Math.min(a, b),
      Math.max(a, b),
      Math.max(2, Math.floor(bounds.width / 90)),
    );
    for (const tick of ticks) {
      const bin = batchRadialBin(tick.value, batch.x);
      if (bin != null) ctx.fillText(tick.label, px(bin), size.height - 26);
    }
    ctx.fillStyle = typography.muted;
    ctx.fillText(
      unitLabel(batch.unit),
      bounds.left + bounds.width / 2,
      size.height - 6,
    );
    ctx.fillStyle = typography.muted;
    ctx.textAlign = "right";
    const stride = Math.max(
      1,
      Math.ceil((v.yMax - v.yMin) / Math.max(1, bounds.height / 42)),
    );
    const frameTicks: number[] = [];
    for (
      let i = Math.max(0, Math.floor(v.yMin));
      i < Math.min(rows, Math.ceil(v.yMax));
      i += stride
    ) {
      frameTicks.push(i + 1);
      ctx.fillText(String(i + 1), bounds.left - 9, py(i + 0.5) + 4);
    }
    c.dataset.frameTicks = JSON.stringify(frameTicks);
  }, [
    typography.muted,
    typography.mono,
    size,
    bitmap,
    nav.view,
    nav.selection,
    batch.selected,
    batch.unit,
    zoomMode,
    position,
    phaseLines,
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
      ? {
          index,
          bin,
          radial: radial(d.x),
          resolution: Math.abs(
            radial(d.x + (nav.view.xMax - nav.view.xMin) / bounds.width) -
              radial(d.x),
          ),
        }
      : null;
  };
  return (
    <div ref={host} className="batch-heatmap">
      <canvas
        ref={canvas}
        data-testid="batch-heatmap"
        data-plot-font-size={typography.size}
        data-plot-left={bounds.left}
        data-plot-top={bounds.top}
        data-plot-width={bounds.width}
        data-plot-height={bounds.height}
        data-unit={batch.unit}
        data-intensity-scale={log ? "log" : sqrt ? "sqrt" : "linear"}
        data-zoom-mode={zoomMode}
        data-phase-line-count={phaseLines?.length ?? 0}
        data-linked-position={
          position
            ? (radialValues(
                position.x,
                position.unit,
                batch.wavelength ?? undefined,
              )[batch.unit] ?? undefined)
            : undefined
        }
        data-view-x-min={nav.view.xMin}
        data-view-x-max={nav.view.xMax}
        data-view-y-min={nav.view.yMin}
        data-view-y-max={nav.view.yMax}
        aria-label="Batch intensity overview"
        aria-description="Vertical axis: frame number, starting at 1."
        tabIndex={0}
        onContextMenu={(e) => e.preventDefault()}
        onPointerDown={(e) => {
          e.currentTarget.focus();
          nav.onPointerDown(e, true, true);
        }}
        onPointerMove={(e) => {
          nav.onPointerMove(e);
          const p = hit(e);
          if (!p) {
            reportPlot("batch", null);
            return;
          }
          const fields = [
            {
              label: "Frame",
              value: String(p.index + 1),
              kind: "pixel" as const,
            },
            {
              label: "I",
              value: intensityValue(values[p.index * cols + p.bin]),
              kind: "intensity" as const,
            },
            ...radialFields(
              p.radial,
              batch.unit,
              batch.wavelength ?? undefined,
              p.resolution,
            ),
          ];
          reportPlot("batch", {
            fields,
            text: fields.map((f) => `${f.label} ${f.value}`).join(" · "),
            hint: `Click to select a frame and radial position. Drag for ${zoomMode === "horizontal" ? "X-range" : "rectangle"} zoom; right drag to pan.`,
          });
        }}
        onPointerLeave={() => reportPlot("batch", null)}
        onPointerUp={(e) => {
          const gesture = nav.onPointerUp(e),
            p = hit(e);
          if (gesture === "click" && p && ready)
            onSelect(p.index, { x: p.radial, unit: batch.unit });
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
      <div className="batch-normalize-toggle">
        <PlotToggle
          label="Normalize batch"
          title={
            batch.normalized
              ? "Restore original batch intensities"
              : normalizationRegion
                ? `Normalize over ${scientificValue(normalizationRegion.minimum)}–${scientificValue(normalizationRegion.maximum)} ${unitLabel(batch.unit)}; edit the region in Options`
                : "Set a normalization region in Options"
          }
          pressed={batch.normalized}
          disabled={!ready || (!batch.normalized && !batch.normalizationRegion)}
          onClick={onNormalize}
        >
          <Equal size={15} aria-hidden="true" />
        </PlotToggle>
      </div>
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

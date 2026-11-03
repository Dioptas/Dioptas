import { useEffect, useMemo, useRef, useState } from "react";
import type { Cake, Palette, Raster, Tool, RingOverlay } from "./types";
import type { MaskOverlay } from "./maskDomain";
import { ByteCache, decodeRaster } from "./rasterTransfer";
import { colorsFor } from "./colorMaps";
import { number, unitLabel } from "./types";
import { linearAxisTicks, linearTicks } from "./plotTicks";
import { PlotZoomControls } from "./PlotZoomControls";
import {
  usePlotNavigation,
  usePlotWheel,
  type ZoomMode,
} from "./usePlotNavigation";

const EMPTY_PEAKS: {
  x: number;
  y: number;
  ring: number;
  selected?: boolean;
}[] = [];
const EMPTY_RINGS: RingOverlay[] = [];
const EMPTY_CONTOURS: number[][][] = [];
const EMPTY_CALIBRANT_LINES: { ring: number; twoTheta: number }[] = [];

// Keep recently colour-mapped images without retaining their source buffers.
const rendered = new ByteCache<string, HTMLCanvasElement>(96 * 1024 * 1024, 12);
export function RasterView({
  raster,
  mask,
  limits,
  log,
  palette,
  tool = "pan",
  radius = 20,
  busy,
  resetKey = 0,
  onStroke,
  onHover,
  cake = false,
  zoomMode = "rectangle",
  onZoomMode,
  onPick,
  onInspect,
  linkedPosition,
  calibrantLines = EMPTY_CALIBRANT_LINES,
  showNumbers = false,
  activeRing,
  currentPeakRing = activeRing,
  maskOpacity = 0.72,
  imagePadding = 0,
  overlay,
  roi,
  onImageDoubleClick,
  peaks = EMPTY_PEAKS,
  rings = EMPTY_RINGS,
  contours = EMPTY_CONTOURS,
}: {
  raster: Raster;
  mask?: Raster;
  limits?: [number, number];
  log: boolean;
  palette: Palette;
  tool?: Tool;
  radius?: number;
  busy?: boolean;
  resetKey?: number;
  cake?: boolean;
  zoomMode?: ZoomMode;
  onZoomMode?: (mode: ZoomMode) => void;
  onStroke?: (points: number[][], erase: boolean) => void;
  onHover?: (
    point: { x: number; y: number; value: number | null } | null,
  ) => void;
  onPick?: (point: { x: number; y: number }) => void;
  onInspect?: (point: { x: number; y: number }) => void;
  linkedPosition?: number;
  calibrantLines?: { ring: number; twoTheta: number; color?: string }[];
  showNumbers?: boolean;
  activeRing?: number;
  currentPeakRing?: number;
  maskOpacity?: number;
  imagePadding?: number;
  overlay?: MaskOverlay;
  roi?: [number, number, number, number] | null;
  onImageDoubleClick?: () => void;
  peaks?: { x: number; y: number; ring: number; selected?: boolean }[];
  rings?: RingOverlay[];
  contours?: number[][][];
}) {
  const container = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 500, height: 380 });
  const [cakeAxisWidth, setCakeAxisWidth] = useState(60);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const [stroke, setStroke] = useState<number[][]>([]);
  const painting = tool === "mask" || tool === "erase";
  const drag = useRef<{ x: number; y: number; points: number[][] } | null>(
    null,
  );
  const data = useMemo(() => decodeRaster(raster), [raster.data, raster.dtype]);
  const maskData = useMemo(
    () => (mask ? decodeRaster(mask) : null),
    [mask?.data, mask?.dtype],
  );
  const [lower, upper] = limits ?? raster.limits;
  const colourImage = useMemo(() => {
    const cacheKey = raster.bufferId
      ? JSON.stringify([
          "colour",
          raster.bufferId,
          raster.dtype,
          raster.width,
          raster.height,
          lower,
          upper,
          log,
          palette,
        ])
      : null;
    const cached = cacheKey ? rendered.get(cacheKey) : undefined;
    if (cached) return cached;
    const offscreen = document.createElement("canvas");
    offscreen.width = raster.width;
    offscreen.height = raster.height;
    const context = offscreen.getContext("2d")!;
    const pixels = context.createImageData(raster.width, raster.height);
    const span = Math.max(upper - lower, 1e-12);
    const ramp = colorsFor(palette),
      last = ramp.length - 1;
    const logSpan = Math.log1p(span);
    for (let i = 0; i < data.length; i++) {
      const value = data[i];
      const t = log
        ? Math.log1p(Math.max(0, value - lower)) / logSpan
        : (value - lower) / span;
      const k = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0)) * last;
      const index = Math.min(Math.floor(k), last - 1),
        fraction = k - index;
      const a = ramp[index],
        b = ramp[index + 1];
      const valid = Number.isFinite(value);
      for (let c = 0; c < 3; c++) {
        const intensity = valid
          ? Math.round(a[c] * (1 - fraction) + b[c] * fraction)
          : c === 0
            ? 23
            : c === 1
              ? 25
              : 30;
        pixels.data[4 * i + c] = intensity;
      }
      pixels.data[4 * i + 3] = 255;
    }
    context.putImageData(pixels, 0, 0);
    if (cacheKey)
      rendered.set(cacheKey, offscreen, 4 * raster.width * raster.height);
    return offscreen;
  }, [
    raster.data,
    raster.bufferId,
    raster.dtype,
    raster.width,
    raster.height,
    data,
    lower,
    upper,
    log,
    palette,
  ]);
  const image = useMemo(() => {
    if (!maskData) return colourImage;
    const cacheKey =
      raster.bufferId && mask?.bufferId
        ? JSON.stringify([
            "mask",
            raster.bufferId,
            raster.dtype,
            raster.width,
            raster.height,
            mask.bufferId,
            lower,
            upper,
            log,
            palette,
            maskOpacity,
          ])
        : null;
    const cached = cacheKey ? rendered.get(cacheKey) : undefined;
    if (cached) return cached;
    // Reuse the unchanged detector colours. Drawing or changing opacity only
    // blends the mask pixels, without repeating log scaling or colour mapping.
    const pixels = colourImage
      .getContext("2d")!
      .getImageData(0, 0, raster.width, raster.height);
    const maskColor = [255, 0, 0];
    for (let i = 0; i < maskData.length; i++) {
      if (!maskData[i]) continue;
      for (let c = 0; c < 3; c++)
        pixels.data[4 * i + c] =
          maskColor[c] * maskOpacity +
          pixels.data[4 * i + c] * (1 - maskOpacity);
    }
    const offscreen = document.createElement("canvas");
    offscreen.width = raster.width;
    offscreen.height = raster.height;
    offscreen.getContext("2d")!.putImageData(pixels, 0, 0);
    if (cacheKey)
      rendered.set(cacheKey, offscreen, 4 * raster.width * raster.height);
    return offscreen;
  }, [
    colourImage,
    maskData,
    mask?.bufferId,
    raster.bufferId,
    raster.dtype,
    raster.width,
    raster.height,
    lower,
    upper,
    log,
    palette,
    maskOpacity,
  ]);
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
    setStroke([]);
  }, [raster.fullWidth, raster.fullHeight, resetKey]);
  const left = cake ? cakeAxisWidth : imagePadding,
    right = cake ? 22 : imagePadding,
    top = cake ? 20 : imagePadding,
    bottom = cake ? 44 : imagePadding;
  const plotWidth = Math.max(1, size.width - left - right),
    plotHeight = Math.max(1, size.height - top - bottom);
  const fitX = cake
    ? plotWidth / raster.fullWidth
    : Math.min(plotWidth / raster.fullWidth, plotHeight / raster.fullHeight);
  const fitY = cake ? plotHeight / raster.fullHeight : fitX;
  const fitWidth = plotWidth / fitX,
    fitHeight = plotHeight / fitY;
  const navigation = usePlotNavigation(
    {
      xMin: (raster.fullWidth - fitWidth) / 2,
      xMax: (raster.fullWidth + fitWidth) / 2,
      yMin: (raster.fullHeight - fitHeight) / 2,
      yMax: (raster.fullHeight + fitHeight) / 2,
    },
    { left, top, width: plotWidth, height: plotHeight },
    !cake,
    zoomMode,
  );
  usePlotWheel(canvas, navigation.onWheel);
  const view = navigation.view;
  const sx = plotWidth / (view.xMax - view.xMin),
    sy = plotHeight / (view.yMax - view.yMin);
  const ox = left - view.xMin * sx,
    oy = top + (view.yMax - raster.fullHeight) * sy;
  const zoom = fitWidth / (view.xMax - view.xMin);
  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!context || !canvas.current) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.current.width = Math.round(size.width * dpr);
    canvas.current.height = Math.round(size.height * dpr);
    context.scale(dpr, dpr);
    // Resizing clears the canvas; transparent margins reveal the workspace surface.
    context.save();
    context.beginPath();
    context.rect(left, top, plotWidth, plotHeight);
    context.clip();
    context.imageSmoothingEnabled = false;
    context.translate(ox, oy + raster.fullHeight * sy);
    context.scale(1, -1);
    context.drawImage(
      image,
      0,
      0,
      raster.fullWidth * sx,
      raster.fullHeight * sy,
    );
    context.restore();
    context.save();
    context.beginPath();
    context.rect(left, top, plotWidth, plotHeight);
    context.clip();
    if (!cake) {
      const labels: { x: number; y: number; text: string; active: boolean }[] =
        [];
      const numbered = new Set<number>();
      const ordered = [...rings].sort(
        (a, b) => Number(a.ring === activeRing) - Number(b.ring === activeRing),
      );
      for (const ring of ordered) {
        const active = ring.ring === activeRing,
          linked = ring.ring < 0;
        const path = () => {
          context.beginPath();
          ring.points.forEach(([x, y], i) => {
            const px = ox + x * sx,
              py = oy + (raster.fullHeight - y) * sy;
            if (i) context.lineTo(px, py);
            else context.moveTo(px, py);
          });
        };
        context.setLineDash([]);
        if (linked) {
          path();
          context.strokeStyle = "#03070ce6";
          context.lineWidth = 3.5;
          context.stroke();
        }
        path();
        context.strokeStyle =
          ring.color ??
          (linked ? "#83f5d0" : active ? "#ff4040d9" : "#ff4040b3");
        context.lineWidth = active ? 2.2 : linked ? 2 : 0.8;
        context.stroke();
        if (
          (showNumbers || active) &&
          ring.ring > 0 &&
          !numbered.has(ring.ring)
        ) {
          const angle = ring.ring * 0.65;
          const tx = left + plotWidth * (0.5 + 0.32 * Math.cos(angle)),
            ty = top + plotHeight * (0.5 + 0.32 * Math.sin(angle));
          const candidates = ring.points
            .map(([x, y]) => ({
              x: ox + x * sx,
              y: oy + (raster.fullHeight - y) * sy,
            }))
            .filter(
              (p) =>
                p.x > left + 20 &&
                p.x < left + plotWidth - 24 &&
                p.y > top + 18 &&
                p.y < top + plotHeight - 16,
            )
            .sort(
              (a, b) =>
                Math.hypot(a.x - tx, a.y - ty) - Math.hypot(b.x - tx, b.y - ty),
            );
          const point = candidates.find(
            (p) =>
              active ||
              labels.every(
                (other) =>
                  Math.abs(other.x - p.x) > 30 || Math.abs(other.y - p.y) > 23,
              ),
          );
          if (point) {
            labels.push({
              ...point,
              text: String(ring.ring),
              active,
            });
            numbered.add(ring.ring);
          }
        }
      }
      context.font = "400 13px -apple-system, sans-serif";
      context.textAlign = "left";
      for (const label of labels) {
        const width = context.measureText(label.text).width + 10;
        context.fillStyle = "#202226dd";
        context.beginPath();
        context.roundRect(label.x + 3, label.y - 18, width, 22, 3);
        context.fill();
        context.fillStyle = "#ff4040";
        context.fillText(label.text, label.x + 8, label.y - 2);
      }
      context.strokeStyle = "#ffffff88";
      context.lineWidth = 1;
      for (const contour of contours) {
        context.beginPath();
        contour.forEach(([x, y], i) => {
          const px = ox + x * sx,
            py = oy + (raster.fullHeight - y) * sy;
          if (i) context.lineTo(px, py);
          else context.moveTo(px, py);
        });
        context.stroke();
      }
      // Start with Qt's 7/9 px dots at fit, then grow gently with zoom so
      // picked points remain visible without covering the enlarged peaks.
      // Orange for the current ring, red otherwise, white selection outline.
      // Draw selected groups last so overlapping picks cannot hide them.
      const peakScale = Math.min(2.5, Math.sqrt(Math.max(1, zoom)));
      const orderedPeaks = [...peaks].sort(
        (a, b) => Number(!!a.selected) - Number(!!b.selected),
      );
      for (const peak of orderedPeaks) {
        const x = ox + (peak.x + 0.5) * sx,
          y = oy + (raster.fullHeight - peak.y - 0.5) * sy;
        context.fillStyle =
          peak.ring === currentPeakRing ? "#ff8c00" : "#ff0000";
        context.strokeStyle = peak.selected
          ? "#ffffff"
          : "rgba(255, 255, 255, 0.353)";
        context.lineWidth = peak.selected ? 2 : 1;
        context.beginPath();
        context.arc(
          x,
          y,
          (peak.selected ? 4.5 : 3.5) * peakScale,
          0,
          Math.PI * 2,
        );
        context.fill();
        context.stroke();
      }
    }
    if (cake) {
      const range = (raster as Cake).radialRange;
      const calibrantWidthBoost = Math.min(
        2,
        0.6 * Math.log2(Math.max(1, zoom)),
      );
      const lineX = (twoTheta: number) =>
        ox +
        ((twoTheta - range[0]) / (range[1] - range[0])) * raster.fullWidth * sx;
      let lastLabelRight = -Infinity;
      context.font = "400 13px -apple-system, sans-serif";
      context.textAlign = "left";
      for (const line of calibrantLines) {
        const x = lineX(line.twoTheta);
        if (!Number.isFinite(x) || x < left || x > left + plotWidth) continue;
        const active = line.ring === activeRing;
        context.strokeStyle =
          line.color ?? (active ? "#ff4040d9" : "#ff4040b3");
        context.lineWidth =
          (active ? 2.2 : 0.8) + (line.color ? 0 : calibrantWidthBoost);
        context.beginPath();
        context.moveTo(x, top);
        context.lineTo(x, top + plotHeight);
        context.stroke();
        if (showNumbers) {
          const text = String(line.ring);
          const width = context.measureText(text).width + 10;
          const labelX = Math.min(x + 3, left + plotWidth - width);
          if (labelX < lastLabelRight + 6) continue;
          context.fillStyle = "#202226dd";
          context.beginPath();
          context.roundRect(labelX, top + 4, width, 22, 3);
          context.fill();
          context.fillStyle = "#ff4040";
          context.fillText(text, labelX + 5, top + 20);
          lastLabelRight = labelX + width;
        }
      }
      if (linkedPosition !== undefined) {
        const x = lineX(linkedPosition);
        context.strokeStyle = "#8af0c4";
        context.lineWidth = 1.5;
        context.beginPath();
        context.moveTo(x, top);
        context.lineTo(x, top + plotHeight);
        context.stroke();
      }
    }
    if (navigation.selection) {
      const { start, end } = navigation.selection;
      context.fillStyle = "#ff950025";
      context.strokeStyle = "#ff9500";
      context.lineWidth = 1;
      context.fillRect(
        Math.min(start.x, end.x),
        Math.min(start.y, end.y),
        Math.abs(end.x - start.x),
        Math.abs(end.y - start.y),
      );
      context.strokeRect(
        Math.min(start.x, end.x),
        Math.min(start.y, end.y),
        Math.abs(end.x - start.x),
        Math.abs(end.y - start.y),
      );
    }
    if (stroke.length) {
      context.fillStyle =
        tool === "erase" ? "rgba(101,197,139,.5)" : "rgba(255,0,0,.5)";
      for (const [x, y] of stroke) {
        context.beginPath();
        context.ellipse(
          ox + x * sx,
          oy + (raster.fullHeight - y) * sy,
          radius * sx,
          radius * sy,
          0,
          0,
          Math.PI * 2,
        );
        context.fill();
      }
    }
    if (roi && !cake) {
      const [rowMin, rowMax, colMin, colMax] = roi;
      const x0 = ox + colMin * sx,
        x1 = ox + colMax * sx;
      const y0 = oy + (raster.fullHeight - rowMax) * sy,
        y1 = oy + (raster.fullHeight - rowMin) * sy;
      context.fillStyle = "#00000080";
      context.beginPath();
      context.rect(left, top, plotWidth, plotHeight);
      context.rect(x0, y0, x1 - x0, y1 - y0);
      context.fill("evenodd");
      context.strokeStyle = "#ff9500";
      context.lineWidth = 1.5;
      context.strokeRect(x0, y0, x1 - x0, y1 - y0);
    }
    if (overlay && !cake) {
      context.strokeStyle = overlay.erase ? "#87e4ae" : "#ff0000";
      context.fillStyle = overlay.erase ? "#65c58b30" : "#ff000030";
      context.lineWidth = 1.5;
      for (const path of overlay.paths) {
        context.beginPath();
        path.forEach(([x, y], i) => {
          const px = ox + x * sx,
            py = oy + (raster.fullHeight - y) * sy;
          if (i) context.lineTo(px, py);
          else context.moveTo(px, py);
        });
        if (path.length > 2) {
          context.closePath();
          context.fill();
        }
        context.stroke();
      }
      if (overlay.ellipse) {
        const e = overlay.ellipse;
        context.beginPath();
        context.ellipse(
          ox + e.cx * sx,
          oy + (raster.fullHeight - e.cy) * sy,
          e.rx * sx,
          e.ry * sy,
          0,
          0,
          Math.PI * 2,
        );
        context.fill();
        context.stroke();
      }
    }
    if (cursor && (tool === "mask" || tool === "erase") && !cake) {
      context.strokeStyle = tool === "erase" ? "#87e4ae" : "#ff0000";
      context.lineWidth = 1;
      context.beginPath();
      context.ellipse(
        cursor.x,
        cursor.y,
        radius * sx,
        radius * sy,
        0,
        0,
        Math.PI * 2,
      );
      context.stroke();
    }
    context.restore();
    if (cake) {
      context.font = "13px ui-monospace, SFMono-Regular, monospace";
      context.fillStyle = "#77828d";
      context.strokeStyle = "#35404a";
      context.lineWidth = 1;
      const { radialRange: xr, azimuthRange: yr } = raster as Cake;
      const radial = (pixel: number) =>
        xr[0] + (pixel / raster.fullWidth) * (xr[1] - xr[0]);
      const azimuth = (pixel: number) =>
        yr[0] + (pixel / raster.fullHeight) * (yr[1] - yr[0]);
      const xMin = radial(view.xMin),
        xMax = radial(view.xMax);
      const yMin = azimuth(view.yMin),
        yMax = azimuth(view.yMax);
      const yAxis = linearAxisTicks(
        yMin,
        yMax,
        Math.max(1, Math.floor(plotHeight / 48)),
      );
      const tickWidth = Math.max(
        0,
        ...yAxis.ticks.map((tick) => context.measureText(tick.label).width),
      );
      // Reserve separate space for the rotated title even without an offset.
      setCakeAxisWidth(Math.max(60, Math.ceil(tickWidth) + 36));
      let intervals = Math.max(1, Math.floor(plotWidth / 80));
      let xTicks = linearTicks(xMin, xMax, intervals);
      while (intervals > 1) {
        const widest = Math.max(
          0,
          ...xTicks.map((tick) => context.measureText(tick.label).width),
        );
        const spacing =
          xTicks.length > 1
            ? ((xTicks[1].value - xTicks[0].value) / (xMax - xMin)) * plotWidth
            : plotWidth;
        if (spacing >= widest + 18) break;
        xTicks = linearTicks(xMin, xMax, --intervals);
      }
      context.textAlign = "center";
      for (const tick of xTicks) {
        const x = left + ((tick.value - xMin) / (xMax - xMin)) * plotWidth;
        context.beginPath();
        context.moveTo(x, top + plotHeight);
        context.lineTo(x, top + plotHeight + 4);
        context.stroke();
        const halfLabel = context.measureText(tick.label).width / 2;
        context.fillText(
          tick.label,
          Math.max(halfLabel + 6, Math.min(size.width - halfLabel - 6, x)),
          size.height - 18,
        );
      }
      context.textAlign = "right";
      for (const tick of yAxis.ticks) {
        const y = top + ((yMax - tick.value) / (yMax - yMin)) * plotHeight;
        context.beginPath();
        context.moveTo(left - 4, y);
        context.lineTo(left, y);
        context.stroke();
        context.fillText(tick.label, left - 8, y + 3);
      }
      if (yAxis.annotation) {
        context.textAlign = "left";
        context.fillText(yAxis.annotation, left, top - 6);
      }
      context.fillStyle = "#929ca7";
      context.textAlign = "center";
      context.fillText(
        unitLabel((raster as Cake).unit),
        left + plotWidth / 2,
        size.height - 3,
      );
      context.save();
      context.translate(11, top + plotHeight / 2);
      context.rotate(-Math.PI / 2);
      context.textBaseline = "middle";
      context.fillText("Azimuth (°)", 0, 0);
      context.restore();
    }
  }, [
    image,
    size,
    view.xMin,
    view.xMax,
    view.yMin,
    view.yMax,
    cursor,
    stroke,
    radius,
    tool,
    cake,
    raster,
    sx,
    sy,
    ox,
    oy,
    zoom,
    peaks,
    rings,
    contours,
    navigation.selection,
    linkedPosition,
    calibrantLines,
    showNumbers,
    activeRing,
    currentPeakRing,
    overlay,
    roi,
  ]);
  function position(event: React.PointerEvent<HTMLCanvasElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    const screen = { x: event.clientX - box.left, y: event.clientY - box.top };
    const x = (screen.x - ox) / sx,
      y = raster.fullHeight - (screen.y - oy) / sy;
    return {
      screen,
      point:
        x >= 0 && y >= 0 && x < raster.fullWidth && y < raster.fullHeight
          ? { x, y }
          : null,
    };
  }
  function addPoint(point: { x: number; y: number }) {
    const points = drag.current!.points;
    const last = points.at(-1);
    if (last) {
      const distance = Math.hypot(point.x - last[0], point.y - last[1]);
      const steps = Math.ceil(distance / Math.max(1, radius / 2));
      for (let i = 1; i <= steps && points.length < 9900; i++)
        points.push([
          last[0] + ((point.x - last[0]) * i) / steps,
          last[1] + ((point.y - last[1]) * i) / steps,
        ]);
    } else points.push([point.x, point.y]);
    setStroke([...points]);
  }
  return (
    <div className="raster-container" ref={container}>
      <canvas
        ref={canvas}
        data-testid={cake ? "cake-canvas" : "detector-canvas"}
        aria-label={
          cake
            ? `Azimuthal cake; left-drag ${zoomMode} zoom, right-drag pan, right-click zoom out`
            : painting
              ? "Detector image; click to stamp, left-drag rectangle zoom, Shift-drag paint, right-drag pan, right-click zoom out"
              : "Detector image; left-drag rectangle zoom, right-drag pan, right-click zoom out"
        }
        style={{
          width: "100%",
          height: "100%",
          cursor: "crosshair",
        }}
        data-full-width={raster.fullWidth}
        data-full-height={raster.fullHeight}
        data-plot-left={left}
        data-plot-top={top}
        data-plot-width={plotWidth}
        data-plot-height={plotHeight}
        data-active-ring={activeRing}
        data-intensity-scale={log ? "log" : "linear"}
        data-colour-map={palette}
        data-intensity-min={lower}
        data-intensity-max={upper}
        data-azimuth-min={cake ? (raster as Cake).azimuthRange[0] : undefined}
        data-azimuth-max={cake ? (raster as Cake).azimuthRange[1] : undefined}
        data-ring-count={cake ? calibrantLines.length : rings.length}
        data-linked-position={linkedPosition}
        data-zoom-mode={zoomMode}
        data-view-x-min={view.xMin}
        data-view-x-max={view.xMax}
        data-view-y-min={view.yMin}
        data-view-y-max={view.yMax}
        onDoubleClick={(event) => {
          if (event.button === 0 && !busy) onImageDoubleClick?.();
        }}
        onContextMenu={(event) => event.preventDefault()}
        onAuxClick={(event) => event.preventDefault()}
        onPointerDown={(event) => {
          const brushDrag = painting && event.shiftKey && !event.ctrlKey;
          // Navigation is available in every tool, including while processing.
          if (navigation.onPointerDown(event, !brushDrag || !!busy, cake))
            return;
          if (busy || !brushDrag || event.button !== 0) return;
          const { point, screen } = position(event);
          event.currentTarget.setPointerCapture(event.pointerId);
          drag.current = { x: screen.x, y: screen.y, points: [] };
          if (point) addPoint(point);
        }}
        onPointerMove={(event) => {
          const { point, screen } = position(event);
          setCursor(screen);
          if (point) {
            const x = Math.floor(point.x / raster.step),
              y = Math.floor(point.y / raster.step);
            const value = data[y * raster.width + x];
            onHover?.({
              ...point,
              value: Number.isFinite(value) ? value : null,
            });
          } else onHover?.(null);
          navigation.onPointerMove(event);
          if (drag.current && point) addPoint(point);
        }}
        onPointerUp={(event) => {
          const result = navigation.onPointerUp(event);
          const { point } = position(event);
          if (result === "click" && point && !busy) {
            if (painting) onStroke?.([[point.x, point.y]], tool === "erase");
            else if (tool === "pick") onPick?.(point);
            else onInspect?.(point);
          }
          if (drag.current && point) addPoint(point);
          const points = drag.current?.points;
          drag.current = null;
          if (event.currentTarget.hasPointerCapture(event.pointerId))
            event.currentTarget.releasePointerCapture(event.pointerId);
          if (points?.length) onStroke?.(points, tool === "erase");
          setStroke([]);
        }}
        onPointerCancel={(event) => {
          navigation.onPointerCancel(event);
          drag.current = null;
          setStroke([]);
        }}
        onPointerLeave={() => {
          setCursor(null);
          onHover?.(null);
        }}
      />
      {cake && onZoomMode && (
        <PlotZoomControls
          mode={zoomMode}
          onChange={onZoomMode}
          left={left}
          bottom={bottom}
          label="Cake"
        />
      )}
      <span className="zoom-badge">{number(zoom, 1)}×</span>
    </div>
  );
}

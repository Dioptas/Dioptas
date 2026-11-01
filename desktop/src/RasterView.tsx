import { useEffect, useMemo, useRef, useState } from "react";
import type { Cake, Palette, Raster, Tool, RingOverlay } from "./types";
import type { MaskOverlay } from "./maskDomain";
import { colorsFor } from "./colorMaps";
import { number, unitLabel } from "./types";
import {
  usePlotNavigation,
  usePlotWheel,
  type ZoomMode,
} from "./usePlotNavigation";

function decode(raster: Raster) {
  const raw = atob(raster.data);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  if (raster.dtype === "u8") return bytes;
  // Explicit little-endian payload, independent of host endianness.
  const view = new DataView(bytes.buffer);
  const values = new Float32Array(bytes.length / 4);
  for (let i = 0; i < values.length; i++)
    values[i] = view.getFloat32(i * 4, true);
  return values;
}
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
  onPick,
  onInspect,
  linkedPosition,
  showNumbers = false,
  activeRing,
  maskOpacity = 0.72,
  imagePadding = 4,
  overlay,
  onImageDoubleClick,
  peaks = [],
  rings = [],
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
  onStroke?: (points: number[][], erase: boolean) => void;
  onHover?: (point: { x: number; y: number } | null) => void;
  onPick?: (point: { x: number; y: number }) => void;
  onInspect?: (point: { x: number; y: number }) => void;
  linkedPosition?: number;
  showNumbers?: boolean;
  activeRing?: number;
  maskOpacity?: number;
  imagePadding?: number;
  overlay?: MaskOverlay;
  onImageDoubleClick?: () => void;
  peaks?: { x: number; y: number; ring: number; selected?: boolean }[];
  rings?: RingOverlay[];
}) {
  const container = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 500, height: 380 });
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const [stroke, setStroke] = useState<number[][]>([]);
  const drag = useRef<{ x: number; y: number; points: number[][] } | null>(
    null,
  );
  const data = useMemo(() => decode(raster), [raster]);
  const maskData = useMemo(() => (mask ? decode(mask) : null), [mask]);
  const [lower, upper] = limits ?? raster.limits;
  const image = useMemo(() => {
    const offscreen = document.createElement("canvas");
    offscreen.width = raster.width;
    offscreen.height = raster.height;
    const context = offscreen.getContext("2d")!;
    const pixels = context.createImageData(raster.width, raster.height);
    const span = Math.max(upper - lower, 1e-12);
    const ramp = colorsFor(palette),
      last = ramp.length - 1;
    const logSpan = Math.log1p(span);
    const maskColor = [255, 0, 0];
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
      const valid = Number.isFinite(value),
        masked = maskData?.[i];
      for (let c = 0; c < 3; c++) {
        const intensity = valid
          ? Math.round(a[c] * (1 - fraction) + b[c] * fraction)
          : c === 0
            ? 23
            : c === 1
              ? 25
              : 30;
        pixels.data[4 * i + c] = masked
          ? maskColor[c] * maskOpacity + intensity * (1 - maskOpacity)
          : intensity;
      }
      pixels.data[4 * i + 3] = 255;
    }
    context.putImageData(pixels, 0, 0);
    return offscreen;
  }, [raster, data, maskData, lower, upper, log, palette, maskOpacity]);
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
  const left = cake ? 60 : imagePadding,
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
    context.fillStyle = cake ? "#10151b" : "#101419";
    context.fillRect(0, 0, size.width, size.height);
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
        path();
        context.strokeStyle = "#03070ce6";
        context.lineWidth = active ? 5.5 : 3.5;
        context.stroke();
        path();
        context.strokeStyle = active
          ? "#fff36b"
          : linked
            ? "#83f5d0"
            : "#ffe0a3";
        context.lineWidth = active ? 2.5 : linked ? 2 : 1.35;
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
                p.x < left + plotWidth - (active ? 65 : 24) &&
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
              text: active ? `Ring ${ring.ring}` : String(ring.ring),
              active,
            });
            numbered.add(ring.ring);
          }
        }
      }
      context.font = "600 14px -apple-system, sans-serif";
      context.textAlign = "left";
      for (const label of labels) {
        const width = context.measureText(label.text).width + 10;
        context.fillStyle = label.active ? "#fff36b" : "#10151bf0";
        context.strokeStyle = label.active ? "#10151b" : "#ffe0a3";
        context.lineWidth = 1;
        context.beginPath();
        context.roundRect(label.x + 3, label.y - 18, width, 22, 3);
        context.fill();
        context.stroke();
        context.fillStyle = label.active ? "#171c20" : "#fff0d6";
        context.fillText(label.text, label.x + 8, label.y - 2);
      }
      for (const peak of peaks) {
        const x = ox + (peak.x + 0.5) * sx,
          y = oy + (raster.fullHeight - peak.y - 0.5) * sy;
        context.strokeStyle = ["#eebc7e", "#8bd0c4", "#c6a1d6", "#9bbdeb"][
          (peak.ring - 1) % 4
        ];
        context.lineWidth = peak.selected ? 2 : 1.5;
        context.beginPath();
        context.arc(x, y, peak.selected ? 5 : 3.5, 0, Math.PI * 2);
        context.stroke();
      }
    }
    if (cake && linkedPosition !== undefined) {
      const range = (raster as Cake).radialRange;
      const x =
        ox +
        ((linkedPosition - range[0]) / (range[1] - range[0])) *
          raster.fullWidth *
          sx;
      context.strokeStyle = "#8af0c4";
      context.lineWidth = 1.5;
      context.beginPath();
      context.moveTo(x, top);
      context.lineTo(x, top + plotHeight);
      context.stroke();
    }
    if (navigation.selection) {
      const { start, end } = navigation.selection;
      context.fillStyle = "#edbc8025";
      context.strokeStyle = "#edbc80";
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
      context.fillStyle = "rgba(255,0,0,.5)";
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
      context.strokeStyle = tool === "erase" ? "#d4ece4" : "#ff0000";
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
      for (let i = 0; i <= 4; i++) {
        const x = left + (plotWidth * i) / 4;
        const px = (x - ox) / sx;
        context.beginPath();
        context.moveTo(x, top + plotHeight);
        context.lineTo(x, top + plotHeight + 4);
        context.stroke();
        context.textAlign = "center";
        const xr = (raster as Cake).radialRange;
        context.fillText(
          number(
            cake ? xr[0] + (px / raster.fullWidth) * (xr[1] - xr[0]) : px,
            cake ? 1 : 0,
          ),
          x,
          size.height - 18,
        );
        const y = top + (plotHeight * i) / 4;
        const py = raster.fullHeight - (y - oy) / sy;
        const yr = (raster as Cake).azimuthRange;
        context.textAlign = "right";
        context.fillText(
          number(
            cake ? yr[0] + (py / raster.fullHeight) * (yr[1] - yr[0]) : py,
            0,
          ),
          left - 8,
          y + 3,
        );
      }
      context.fillStyle = "#929ca7";
      context.textAlign = "center";
      context.fillText(
        cake ? unitLabel((raster as Cake).unit) : "x · pixels",
        left + plotWidth / 2,
        size.height - 3,
      );
      context.save();
      context.translate(11, top + plotHeight / 2);
      context.rotate(-Math.PI / 2);
      context.fillText(cake ? "Azimuth (°)" : "y · pixels", 0, 0);
      context.restore();
    }
  }, [
    image,
    size,
    view,
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
    peaks,
    rings,
    navigation.selection,
    linkedPosition,
    showNumbers,
    activeRing,
    overlay,
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
            ? "Azimuthal cake; left-drag rectangle zoom, right-drag pan, right-click zoom out"
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
        data-ring-count={rings.length}
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
          const painting = tool === "mask" || tool === "erase";
          // Navigation is available in every tool, including while processing.
          if (navigation.onPointerDown(event, !painting || !!busy)) return;
          if (busy || !painting || event.button !== 0 || event.ctrlKey) return;
          const { point, screen } = position(event);
          event.currentTarget.setPointerCapture(event.pointerId);
          drag.current = { x: screen.x, y: screen.y, points: [] };
          if (point) addPoint(point);
        }}
        onPointerMove={(event) => {
          const { point, screen } = position(event);
          setCursor(screen);
          onHover?.(point);
          navigation.onPointerMove(event);
          if (drag.current && point) addPoint(point);
        }}
        onPointerUp={(event) => {
          const result = navigation.onPointerUp(event);
          const { point } = position(event);
          if (result === "click" && point && !busy) {
            if (tool === "pick") onPick?.(point);
            else onInspect?.(point);
          }
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
      <span className="zoom-badge">{number(zoom, 1)}×</span>
    </div>
  );
}

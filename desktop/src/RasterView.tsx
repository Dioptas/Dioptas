import { useCakeAxisGesture } from "./CakeProfileWorkspace";
import { usePlotTypography } from "./usePlotTypography";
import { navigationTrace } from "./navigationTiming";
import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type Ref,
} from "react";
import type { Cake, Palette, Raster, Tool, RingOverlay } from "./types";
import type { MaskOverlay } from "./maskDomain";
import {
  cakeSourcePixel,
  createCakeRadialAxis,
  type CakeRadialAxis,
} from "./cakeRadialAxis";
import type { PlotViewport } from "./plotViewport";
import { decodeRaster } from "./rasterTransfer";
import { colorsFor } from "./colorMaps";
import { WebGLRaster } from "./WebGLRaster";
import { rasterCanvas } from "./rasterCanvas";
import { number, unitLabel } from "./types";
import { linearAxisTicks } from "./plotTicks";
import { PlotZoomControls } from "./PlotZoomControls";
import {
  roiHandles,
  useRoiInteraction,
  type DetectorRoi,
} from "./useRoiInteraction";
import { POSITION_LINE_COLOR } from "./plotColors";
import {
  drawRangeSelection,
  RANGE_SELECTION_COLOR,
} from "./drawRangeSelection";
import {
  isPlotSecondaryGesture,
  usePlotNavigation,
  usePlotWheel,
  type ZoomMode,
} from "./usePlotNavigation";

export interface RasterExport {
  png: () => string;
}

const EMPTY_PEAKS: {
  x: number;
  y: number;
  ring: number;
  selected?: boolean;
}[] = [];
const EMPTY_RINGS: RingOverlay[] = [];
const EMPTY_CONTOURS: number[][][] = [];
const EMPTY_CALIBRANT_LINES: { ring: number; twoTheta: number }[] = [];

export function RasterView({
  raster,
  viewport,
  exportRef,
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
  onResolution,
  cake = false,
  showCakeAzimuthAxis = true,
  radialAxis,
  zoomMode = "rectangle",
  onZoomMode,
  onPick,
  onInspect,
  linkedPosition,
  clickedPoint,
  calibrantLines = EMPTY_CALIBRANT_LINES,
  showNumbers = false,
  activeRing,
  currentPeakRing = activeRing,
  maskOpacity = 0.72,
  imagePadding = 0,
  overlay,
  roi,
  onRoiChange,
  onImageDoubleClick,
  peaks = EMPTY_PEAKS,
  rings = EMPTY_RINGS,
  contours = EMPTY_CONTOURS,
}: {
  raster: Raster;
  viewport?: PlotViewport;
  exportRef?: Ref<RasterExport>;
  mask?: Raster;
  limits?: [number, number];
  log: boolean;
  palette: Palette;
  tool?: Tool;
  radius?: number;
  busy?: boolean;
  resetKey?: number;
  cake?: boolean;
  showCakeAzimuthAxis?: boolean;
  radialAxis?: CakeRadialAxis;
  zoomMode?: ZoomMode;
  onZoomMode?: (mode: ZoomMode) => void;
  onStroke?: (points: number[][], erase: boolean) => void;
  onHover?: (
    point: {
      x: number;
      y: number;
      value: number | null;
      xResolution?: number;
      yResolution?: number;
    } | null,
  ) => void;
  onResolution?: (resolution: { x: number; y: number }) => void;
  onPick?: (point: { x: number; y: number }) => void;
  onInspect?: (point: {
    x: number;
    y: number;
    value: number | null;
    xResolution?: number;
    yResolution?: number;
  }) => void;
  linkedPosition?: number;
  clickedPoint?: { x: number; y: number } | null;
  calibrantLines?: (Omit<RingOverlay, "points" | "twoTheta"> & {
    twoTheta: number;
  })[];
  showNumbers?: boolean;
  activeRing?: number;
  currentPeakRing?: number;
  maskOpacity?: number;
  imagePadding?: number;
  overlay?: MaskOverlay;
  roi?: DetectorRoi | null;
  onRoiChange?: (roi: DetectorRoi) => Promise<void>;
  onImageDoubleClick?: () => void;
  peaks?: { x: number; y: number; ring: number; selected?: boolean }[];
  rings?: RingOverlay[];
  contours?: number[][][];
}) {
  const container = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 500, height: 380 });
  const [cakeAxisWidth, setCakeAxisWidth] = useState(60);
  const cakeAxis = useMemo(
    () =>
      radialAxis ??
      (cake
        ? createCakeRadialAxis(
            raster as Cake,
            (raster as Cake).unit === "q_A^-1" ? "q_A^-1" : "2th_deg",
          )
        : undefined),
    [radialAxis, cake, raster],
  );
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
  const softwareCache = useRef<{
    colourKey: unknown[];
    key: unknown[];
    colour: HTMLCanvasElement;
    image: HTMLCanvasElement;
  } | null>(null);
  const softwareImage = useCallback(() => {
    const colourKey = [
      data,
      raster.width,
      raster.height,
      lower,
      upper,
      log,
      palette,
    ];
    const key = [...colourKey, maskData, maskOpacity];
    const previous = softwareCache.current;
    if (previous && key.every((v, i) => Object.is(v, previous.key[i])))
      return previous.image;
    const colour =
      previous && colourKey.every((v, i) => Object.is(v, previous.colourKey[i]))
        ? previous.colour
        : rasterCanvas(
            raster,
            data,
            undefined,
            null,
            lower,
            upper,
            log,
            palette,
            0,
          );
    const image = maskData
      ? rasterCanvas(
          raster,
          data,
          mask,
          maskData,
          lower,
          upper,
          log,
          palette,
          maskOpacity,
          colour,
        )
      : colour;
    softwareCache.current = { colourKey, key, colour, image };
    return image;
  }, [raster, data, mask, maskData, lower, upper, log, palette, maskOpacity]);
  const gpuCanvas = useRef<HTMLCanvasElement>(null);
  const gpu = useRef<WebGLRaster | null>(null);
  const [renderer, setRenderer] = useState("pending");
  const [contextVersion, setContextVersion] = useState(0);
  useEffect(() => {
    const element = gpuCanvas.current!;
    let disposed = false;
    const initialize = () => {
      try {
        gpu.current = new WebGLRaster(element);
        setRenderer("webgl2");
      } catch {
        gpu.current = null;
        setRenderer("canvas2d");
      }
      setContextVersion((v) => v + 1);
    };
    const lost = (event: Event) => {
      if (disposed) return;
      event.preventDefault();
      gpu.current = null;
      setRenderer("canvas2d");
    };
    element.addEventListener("webglcontextlost", lost);
    element.addEventListener("webglcontextrestored", initialize);
    initialize();
    return () => {
      disposed = true;
      element.removeEventListener("webglcontextlost", lost);
      element.removeEventListener("webglcontextrestored", initialize);
      gpu.current?.dispose();
      gpu.current = null;
    };
  }, []);
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
  const typography = usePlotTypography(canvas);
  const left = cake ? (showCakeAzimuthAxis ? cakeAxisWidth : 8) : imagePadding,
    right = cake ? 22 : imagePadding,
    top = cake ? 20 : imagePadding,
    bottom = cake ? 44 * typography.scale : imagePadding;
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
    undefined,
    viewport,
  );
  const axisGesture = useCakeAxisGesture("cake", canvas, navigation);
  const [resetSource, setResetSource] = useState([
    raster.fullWidth,
    raster.fullHeight,
    resetKey,
  ]);
  if (
    resetSource[0] !== raster.fullWidth ||
    resetSource[1] !== raster.fullHeight ||
    resetSource[2] !== resetKey
  ) {
    // Standalone rasters reset before committing new pixels. Shared detector
    // views use the viewport's compatibility key instead of an image refresh.
    setResetSource([raster.fullWidth, raster.fullHeight, resetKey]);
    if (!viewport) navigation.reset();
    if (stroke.length) setStroke([]);
  }
  const view = navigation.view;
  const sx = plotWidth / (view.xMax - view.xMin),
    sy = plotHeight / (view.yMax - view.yMin);
  const ox = left - view.xMin * sx,
    oy = top + (view.yMax - raster.fullHeight) * sy;
  useEffect(() => {
    if (size.width > 100 && size.height > 100)
      onResolution?.({ x: 1 / sx, y: 1 / sy });
  }, [onResolution, sx, sy, size.width, size.height]);
  const roiInteraction = useRoiInteraction({
    roi: cake ? null : roi,
    width: raster.fullWidth,
    height: raster.fullHeight,
    projection: { ox, yBase: oy + raster.fullHeight * sy, sx, sy },
    busy,
    onChange: cake ? undefined : onRoiChange,
  });
  const displayedRoi = roiInteraction.roi;
  usePlotWheel(canvas, (event) => {
    if (!roiInteraction.dragging) navigation.onWheel(event);
  });
  const zoom = fitWidth / (view.xMax - view.xMin);
  const editableRoi = !!onRoiChange;
  useLayoutEffect(() => {
    if (!gpu.current) return;
    try {
      navigationTrace("raster-start", {
        bufferId: raster.bufferId,
        kind: cake ? "cake" : "detector",
      });
      gpu.current.draw({
        data,
        mask: maskData,
        width: raster.width,
        height: raster.height,
        colors: colorsFor(palette),
        lower,
        upper,
        log,
        maskOpacity,
        viewport: { ...size, dpr: window.devicePixelRatio || 1 },
        image: {
          x: ox,
          y: oy,
          width: raster.fullWidth * sx,
          height: raster.fullHeight * sy,
        },
        clip: { left, top, width: plotWidth, height: plotHeight },
      });
      navigationTrace("raster-submitted", {
        bufferId: raster.bufferId,
        kind: cake ? "cake" : "detector",
      });
      setRenderer("webgl2");
    } catch {
      // Includes unsupported texture dimensions and GPU allocation failure.
      setRenderer("canvas2d");
    }
  }, [
    data,
    maskData,
    raster.width,
    raster.height,
    raster.fullWidth,
    raster.fullHeight,
    palette,
    lower,
    upper,
    log,
    maskOpacity,
    size,
    ox,
    oy,
    sx,
    sy,
    left,
    top,
    plotWidth,
    plotHeight,
    contextVersion,
  ]);
  const draw = useCallback(
    (output: HTMLCanvasElement, exporting = false) => {
      const context = output.getContext("2d");
      if (!context) return;
      const dpr = exporting
        ? 2048 / Math.max(1, size.width)
        : window.devicePixelRatio || 1;
      const width = Math.max(1, Math.round(size.width * dpr));
      const height = Math.max(1, Math.round(size.height * dpr));
      if (output.width !== width) output.width = width;
      if (output.height !== height) output.height = height;
      context.setTransform(1, 0, 0, 1, 0, 0);
      context.clearRect(0, 0, width, height);
      context.scale(dpr, dpr);
      context.lineWidth = 1;
      context.setLineDash([]);
      // PNG exports use Qt's 2048-pixel width and retain the current plot view.
      if (exporting) {
        context.fillStyle = "#101518";
        context.fillRect(0, 0, size.width, size.height);
      }
      // Resizing clears the canvas; transparent margins reveal the workspace surface.
      context.save();
      context.beginPath();
      context.rect(left, top, plotWidth, plotHeight);
      context.clip();
      if (exporting || renderer === "canvas2d" || !gpu.current) {
        context.imageSmoothingEnabled = false;
        context.translate(ox, oy + raster.fullHeight * sy);
        context.scale(1, -1);
        context.drawImage(
          softwareImage(),
          0,
          0,
          raster.fullWidth * sx,
          raster.fullHeight * sy,
        );
      }
      context.restore();
      context.save();
      context.beginPath();
      context.rect(left, top, plotWidth, plotHeight);
      context.clip();
      if (!cake) {
        const labels: {
          x: number;
          y: number;
          text: string;
          active: boolean;
        }[] = [];
        const numbered = new Set<number>();
        const ordered = [...rings].sort(
          (a, b) =>
            Number(a.ring === activeRing) - Number(b.ring === activeRing),
        );
        for (const ring of ordered) {
          const active = ring.ring === activeRing,
            linked = ring.ring <= 0 && !ring.color;
          if (exporting && linked) continue;
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
            (linked ? POSITION_LINE_COLOR : active ? "#ff4040d9" : "#ff4040b3");
          context.lineWidth =
            ring.lineWidth ?? (active ? 2.2 : linked ? 2 : 0.8);
          context.globalAlpha = ring.opacity ?? 1;
          context.stroke();
          context.globalAlpha = 1;
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
                  Math.hypot(a.x - tx, a.y - ty) -
                  Math.hypot(b.x - tx, b.y - ty),
              );
            const point = candidates.find(
              (p) =>
                active ||
                labels.every(
                  (other) =>
                    Math.abs(other.x - p.x) > 30 ||
                    Math.abs(other.y - p.y) > 23,
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
        context.font = typography.text;
        context.textAlign = "left";
        for (const label of labels) {
          const width = context.measureText(label.text).width + 10;
          const labelX = Math.max(
            left,
            Math.min(label.x + 3, left + plotWidth - width),
          );
          const labelY = Math.max(
            top,
            Math.min(label.y - 18, top + plotHeight - 22),
          );
          context.fillStyle = "#202226dd";
          context.beginPath();
          context.roundRect(labelX, labelY, width, 22, 3);
          context.fill();
          context.fillStyle = "#ff4040";
          context.fillText(label.text, labelX + 5, labelY + 16);
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
        const calibrantWidthBoost = Math.min(
          2,
          0.6 * Math.log2(Math.max(1, zoom)),
        );
        const lineX = (twoTheta: number) =>
          ox + cakeSourcePixel(raster as Cake, twoTheta) * sx;
        let lastLabelRight = -Infinity;
        context.font = typography.text;
        context.textAlign = "left";
        for (const line of calibrantLines) {
          const x = lineX(line.twoTheta);
          if (!Number.isFinite(x) || x < left || x > left + plotWidth) continue;
          const active = line.ring === activeRing;
          context.strokeStyle =
            line.color ?? (active ? "#ff4040d9" : "#ff4040b3");
          context.lineWidth =
            line.lineWidth ??
            (active ? 2.2 : 0.8) + (line.color ? 0 : calibrantWidthBoost);
          context.globalAlpha = line.opacity ?? 1;
          context.beginPath();
          context.moveTo(x, top);
          context.lineTo(x, top + plotHeight);
          context.stroke();
          context.globalAlpha = 1;
          if (showNumbers) {
            const text = String(line.ring);
            const width = context.measureText(text).width + 10;
            const labelX = Math.min(x + 3, left + plotWidth - width);
            const badge = exporting
              ? null
              : container.current?.querySelector<HTMLElement>(".zoom-badge");
            const badgeLeft = size.width - 11 - (badge?.offsetWidth ?? 0);
            const labelTop =
              badge &&
              labelX + width > badgeLeft &&
              top + 4 < 10 + badge.offsetHeight
                ? Math.max(top + 4, 14 + badge.offsetHeight)
                : top + 4;
            if (labelX < lastLabelRight + 6) continue;
            context.fillStyle = "#202226dd";
            context.beginPath();
            context.roundRect(labelX, labelTop, width, 22, 3);
            context.fill();
            context.fillStyle = "#ff4040";
            context.fillText(text, labelX + 5, labelTop + 16);
            lastLabelRight = labelX + width;
          }
        }
        if (linkedPosition !== undefined && !exporting) {
          const x = lineX(linkedPosition);
          context.strokeStyle = POSITION_LINE_COLOR;
          context.lineWidth = 1.5;
          context.beginPath();
          context.moveTo(x, top);
          context.lineTo(x, top + plotHeight);
          context.stroke();
        }
      }
      if (clickedPoint && !exporting) {
        const x = ox + clickedPoint.x * sx;
        const y = oy + (raster.fullHeight - clickedPoint.y) * sy;
        // A screen-sized cross stays visible at any zoom, like Qt's click item.
        const cross = () => {
          context.beginPath();
          context.moveTo(x - 7, y);
          context.lineTo(x + 7, y);
          context.moveTo(x, y - 7);
          context.lineTo(x, y + 7);
          context.stroke();
        };
        context.strokeStyle = "#101010";
        context.lineWidth = 4;
        cross();
        context.strokeStyle = POSITION_LINE_COLOR;
        context.lineWidth = 1.5;
        cross();
      }
      if (navigation.selection && !exporting) {
        const { start, end } = navigation.selection;
        const x = Math.min(start.x, end.x),
          y = Math.min(start.y, end.y),
          width = Math.abs(end.x - start.x),
          height = Math.abs(end.y - start.y);
        if (cake && zoomMode === "horizontal") {
          drawRangeSelection(
            context,
            x,
            x + width,
            y,
            height,
            RANGE_SELECTION_COLOR,
          );
        } else {
          context.fillStyle = RANGE_SELECTION_COLOR + "25";
          context.strokeStyle = RANGE_SELECTION_COLOR;
          context.lineWidth = 1;
          context.fillRect(x, y, width, height);
          context.strokeRect(x, y, width, height);
        }
      }
      if (stroke.length && !exporting) {
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
      if (displayedRoi && !cake && !exporting) {
        const [rowMin, rowMax, colMin, colMax] = displayedRoi;
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
        if (editableRoi) {
          const { handles } = roiHandles(displayedRoi, {
            ox,
            yBase: oy + raster.fullHeight * sy,
            sx,
            sy,
          });
          context.fillStyle = "#202225";
          for (const [, x, y] of handles) {
            context.fillRect(x - 3, y - 3, 6, 6);
            context.strokeRect(x - 3, y - 3, 6, 6);
          }
        }
      }
      if (overlay && !cake && !exporting) {
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
      if (
        cursor &&
        (tool === "mask" || tool === "erase") &&
        !cake &&
        !exporting
      ) {
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
        context.font = typography.mono;
        context.fillStyle = typography.muted;
        context.strokeStyle = "#35404a";
        context.lineWidth = 1;
        const { azimuthRange: yr } = raster as Cake;
        const azimuth = (pixel: number) =>
          yr[0] + (pixel / raster.fullHeight) * (yr[1] - yr[0]);
        const yMin = azimuth(view.yMin),
          yMax = azimuth(view.yMax);
        const yAxis = linearAxisTicks(
          yMin,
          yMax,
          Math.max(1, Math.floor(plotHeight / (48 * typography.scale))),
        );
        const tickWidth = Math.max(
          0,
          ...yAxis.ticks.map((tick) => context.measureText(tick.label).width),
        );
        // Reserve separate space for the rotated title even without an offset.
        if (showCakeAzimuthAxis)
          setCakeAxisWidth(Math.max(60, Math.ceil(tickWidth) + 36));
        let intervals = Math.max(1, Math.floor(plotWidth / 80));
        let xTicks = cakeAxis!.ticks(view.xMin, view.xMax, intervals);
        while (intervals > 1) {
          const widest = Math.max(
            0,
            ...xTicks.map((tick) => context.measureText(tick.label).width),
          );
          const spacing =
            xTicks.length > 1
              ? Math.min(
                  ...xTicks
                    .slice(1)
                    .map(
                      (tick, index) => (tick.pixel - xTicks[index].pixel) * sx,
                    ),
                )
              : plotWidth;
          if (spacing >= widest + 18) break;
          xTicks = cakeAxis!.ticks(view.xMin, view.xMax, --intervals);
        }
        context.textAlign = "center";
        for (const tick of xTicks) {
          const x = ox + tick.pixel * sx;
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
        if (showCakeAzimuthAxis) {
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
        }
        context.fillStyle = typography.muted;
        context.textAlign = "center";
        context.fillText(
          unitLabel(cakeAxis!.unit) +
            (cakeAxis!.note ? " · conversion unavailable" : ""),
          left + plotWidth / 2,
          size.height - 3,
        );
        if (showCakeAzimuthAxis) {
          context.save();
          context.translate(11, top + plotHeight / 2);
          context.rotate(-Math.PI / 2);
          context.textBaseline = "middle";
          // The optional profile shares this pane at compact window heights.
          // Keep the title inside the canvas when the cake is shallow.
          context.fillText(plotHeight < 120 ? "χ (°)" : "Azimuth (°)", 0, 0);
          context.restore();
        }
      }
    },
    [
      typography.muted,
      typography.mono,
      typography.text,
      softwareImage,
      renderer,
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
      cakeAxis,
      showCakeAzimuthAxis,
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
      clickedPoint,
      zoomMode,
      linkedPosition,
      calibrantLines,
      showNumbers,
      activeRing,
      currentPeakRing,
      overlay,
      displayedRoi,
      editableRoi,
    ],
  );
  useLayoutEffect(() => {
    if (canvas.current) draw(canvas.current);
  }, [draw]);
  useImperativeHandle(
    exportRef,
    () => ({
      png: () => {
        const output = document.createElement("canvas");
        draw(output, true);
        return output.toDataURL("image/png").split(",")[1];
      },
    }),
    [draw],
  );
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
        ref={gpuCanvas}
        className="raster-gpu-layer"
        data-plot-font-size={typography.size}
        data-testid={cake ? "cake-gpu" : "detector-gpu"}
        aria-hidden="true"
        style={{ visibility: renderer === "webgl2" ? "visible" : "hidden" }}
      />
      <canvas
        ref={canvas}
        tabIndex={0}
        onKeyDown={navigation.onKeyDown}
        data-testid={cake ? "cake-canvas" : "detector-canvas"}
        data-plot-font-size={typography.size}
        aria-label={
          cake
            ? `Azimuthal cake; left-drag ${zoomMode} zoom, right-drag pan, right-click zoom out; keyboard arrows pan, +/- zoom, F restores view`
            : displayedRoi && onRoiChange
              ? "Detector image; drag inside the ROI to move, drag edges or corners to resize, Escape cancels; left-drag outside zooms, right-drag pans"
              : painting
                ? "Detector image; click to stamp, left-drag rectangle zoom, Shift-drag paint, right-drag pan, right-click zoom out; keyboard arrows pan, +/- zoom, F restores view"
                : "Detector image; left-drag rectangle zoom, right-drag pan, right-click zoom out; keyboard arrows pan, +/- zoom, F restores view"
        }
        style={{
          width: "100%",
          height: "100%",
          cursor: roiInteraction.cursor(cursor),
        }}
        data-renderer={renderer}
        data-roi={displayedRoi?.join(",")}
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
        title={cakeAxis?.note}
        data-radial-source-unit={cake ? (raster as Cake).unit : undefined}
        data-radial-display-unit={cakeAxis?.unit}
        data-radial-axis-bounds={cakeAxis
          ?.bounds(view.xMin, view.xMax)
          ?.join(",")}
        data-radial-axis-ticks={
          cakeAxis
            ? JSON.stringify(
                cakeAxis.ticks(
                  view.xMin,
                  view.xMax,
                  Math.max(1, Math.floor(plotWidth / 80)),
                ),
              )
            : undefined
        }
        data-radial-axis-note={cakeAxis?.note}
        data-azimuth-min={cake ? (raster as Cake).azimuthRange[0] : undefined}
        data-azimuth-max={cake ? (raster as Cake).azimuthRange[1] : undefined}
        data-shows-azimuth-axis={cake ? showCakeAzimuthAxis : undefined}
        data-ring-count={cake ? calibrantLines.length : rings.length}
        data-click-x={clickedPoint?.x}
        data-click-y={clickedPoint?.y}
        data-linked-position={linkedPosition}
        data-zoom-mode={zoomMode}
        data-view-x-min={view.xMin}
        data-view-x-max={view.xMax}
        data-view-y-min={view.yMin}
        data-view-y-max={view.yMax}
        onDoubleClick={(event) => {
          if (event.button === 0 && !isPlotSecondaryGesture(event) && !busy)
            onImageDoubleClick?.();
        }}
        onContextMenu={(event) => event.preventDefault()}
        onAuxClick={(event) => event.preventDefault()}
        onPointerDown={(event) => {
          if (roiInteraction.onPointerDown(event)) return;
          const brushDrag =
            painting && event.shiftKey && !isPlotSecondaryGesture(event);
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
          if (cake && axisGesture?.move(event)) return;
          const { point, screen } = position(event);
          setCursor(screen);
          if (point) {
            const x = Math.floor(point.x / raster.step),
              y = Math.floor(point.y / raster.step);
            const value = data[y * raster.width + x];
            onHover?.({
              ...point,
              xResolution: 1 / sx,
              yResolution: 1 / sy,
              value: Number.isFinite(value) ? value : null,
            });
          } else onHover?.(null);
          if (roiInteraction.onPointerMove(event)) return;
          navigation.onPointerMove(event);
          if (drag.current && point) addPoint(point);
        }}
        onPointerUp={(event) => {
          if (cake && axisGesture?.finish(event)) return;
          if (roiInteraction.onPointerUp(event)) return;
          const result = navigation.onPointerUp(event);
          const { point } = position(event);
          if (result === "click" && point && !busy) {
            if (painting) onStroke?.([[point.x, point.y]], tool === "erase");
            else if (tool === "pick") onPick?.(point);
            else {
              const value =
                data[
                  Math.floor(point.y / raster.step) * raster.width +
                    Math.floor(point.x / raster.step)
                ];
              onInspect?.({
                ...point,
                xResolution: 1 / sx,
                yResolution: 1 / sy,
                value: Number.isFinite(value) ? value : null,
              });
            }
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
          if (cake && axisGesture?.cancel(event)) return;
          roiInteraction.onPointerCancel();
          navigation.onPointerCancel(event);
          drag.current = null;
          setStroke([]);
        }}
        onLostPointerCapture={roiInteraction.onLostPointerCapture}
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

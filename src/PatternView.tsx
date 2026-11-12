import {
  SvgRecording,
  drawFigureLegends,
  type PlotFigureExport,
} from "./plotFigureExport";
import type { PatternFigureSource } from "./patternFigure";
import { usePlotTypography } from "./usePlotTypography";
import { navigationTrace } from "./navigationTiming";
import {
  WebGLPattern,
  type PatternCurve,
  type PatternFrame,
} from "./WebGLPattern";
import { IntegrationPhaseLegend } from "./IntegrationPhaseLegend";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useImperativeHandle,
  type Ref,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { scientificValue } from "./ScientificNumberInput";
import {
  nearestSample,
  visibleSamples,
  sampleInspectionOrder,
  type InspectionDirection,
} from "./patternSamples";
import type { PlotRange } from "./usePlotNavigation";
import type { PlotViewport } from "./plotViewport";
import type { Pattern, PlotUnit, Unit } from "./types";
import type { PatternHover } from "./plotReadout";
import { unitLabel } from "./types";
import { linearAxisTicks, linearTicks, logTicks } from "./plotTicks";
import { PlotZoomControls } from "./PlotZoomControls";
import { OverlayPlotLegend } from "./OverlayPlotLegend";
import { POSITION_LINE_COLOR } from "./plotColors";
import { scalePhaseLines } from "./phaseLineScaling";
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
  appearance?: "range";
  active?: boolean;
  bounds?: [number, number];
  minWidth?: number;
  movable?: boolean;
};
const EMPTY_REGIONS: PatternRegion[] = [];
const EMPTY_CALIBRANTS: { x: number; ring: number }[] = [];
const EMPTY_CURVES: NonNullable<Pattern["curves"]> = [];
const EMPTY_REFERENCES: NonNullable<Pattern["phaseLines"]> = [];

export function PatternView<U extends PlotUnit = Unit>({
  pattern,
  yLabel = "Intensity (a.u.)",
  showXAxis = true,
  plotLabel = "Integrated diffraction pattern",
  valueLabel,
  onViewChange,
  axisLeft,
  referenceMode = "scaled",
  viewport,
  exportRef,
  patternColor = "#ffffff",
  showPattern = true,
  emphasizePattern = false,
  log,
  sqrt = false,
  antialias = true,
  compact = false,
  autoRange = false,
  onAutoRange,
  zoomMode = "rectangle",
  onZoomMode,
  onPick,
  onInspect,
  onHover,
  onResolution,
  hoverHint,
  linkedPosition,
  activeRing,
  calibrantLines = EMPTY_CALIBRANTS,
  showNumbers = false,
  overlayLegend,
  curves = EMPTY_CURVES,
  referenceLines = EMPTY_REFERENCES,
  regions = EMPTY_REGIONS,
  editRegions = false,
  onRegionChange,
  onRegionSelect,
  onRegionInput,
  onRegionDragStart,
  onRegionCancel,
  regionsUpdating = false,
  onRender,
  curveRenderer = import.meta.env.VITE_DIOPTAS_PATTERN_RENDERER === "canvas2d"
    ? "canvas2d"
    : "webgl2",
}: {
  exportRef?: Ref<PlotFigureExport>;
  curveRenderer?: "canvas2d" | "webgl2";
  onRender?: (sample: {
    cpuMs: number;
    renderer: string;
    xMin: number;
    xMax: number;
    uploads?: number;
    uploadBytes?: number;
  }) => void;
  pattern: Omit<Pattern, "unit"> & { unit: U };
  yLabel?: string;
  showXAxis?: boolean;
  plotLabel?: string;
  valueLabel?: string;
  onViewChange?: (range: PlotRange) => void;
  axisLeft?: number;
  referenceMode?: "scaled" | "full-height";
  viewport?: PlotViewport;
  patternColor?: string;
  showPattern?: boolean;
  emphasizePattern?: boolean;
  log: boolean;
  sqrt?: boolean;
  antialias?: boolean;
  compact?: boolean;
  autoRange?: boolean;
  onAutoRange?: (enabled: boolean) => void;
  zoomMode?: ZoomMode;
  onZoomMode?: (mode: ZoomMode) => void;
  onPick?: (
    x: number,
    mouseY: number,
    resolution: { x: number; y: number },
  ) => void;
  onInspect?: (
    x: number,
    mouseY: number,
    resolution: { x: number; y: number },
  ) => void;
  onHover?: (point: PatternHover<U> | null) => void;
  onResolution?: (x: number) => void;
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
  onRegionSelect?: (name: string) => void;
  onRegionInput?: (name: string, min: number, max: number) => void;
  onRegionDragStart?: () => void;
  onRegionCancel?: () => void;
  regionsUpdating?: boolean;
}) {
  // Parents sometimes pass fresh empty arrays during footer readout updates.
  if (!calibrantLines.length) calibrantLines = EMPTY_CALIBRANTS;
  if (!curves.length) curves = EMPTY_CURVES;
  if (!referenceLines.length) referenceLines = EMPTY_REFERENCES;
  const canvas = useRef<HTMLCanvasElement>(null),
    container = useRef<HTMLDivElement>(null);
  const figureSource = useRef<PatternFigureSource | null>(null);
  const exportDraw =
    useRef<() => ReturnType<PlotFigureExport["capture"]>>(null);
  useImperativeHandle(
    exportRef,
    () => ({
      source: () => {
        if (!figureSource.current)
          throw Error("The pattern has not been rendered yet.");
        return figureSource.current;
      },
      capture: () => {
        if (!exportDraw.current)
          throw Error("The pattern has not been rendered yet.");
        return exportDraw.current();
      },
    }),
    [],
  );
  const renderObserver = useRef(onRender);
  renderObserver.current = onRender;
  const backdrop = useRef<HTMLCanvasElement>(null);
  const gpuCanvas = useRef<HTMLCanvasElement>(null);
  const gpu = useRef<WebGLPattern | null>(null);
  const gpuFrame = useRef<PatternFrame | null>(null);
  const [gpuVersion, setGpuVersion] = useState(0);
  const [activeRenderer, setActiveRenderer] = useState("canvas2d");
  useEffect(() => {
    if (curveRenderer !== "webgl2") return;
    const element = gpuCanvas.current!;
    const initialize = () => {
      try {
        gpu.current = new WebGLPattern(element);
      } catch {
        gpu.current = null;
      }
      setGpuVersion((v) => v + 1);
    };
    const lost = (event: Event) => {
      event.preventDefault();
      gpu.current = null;
      setGpuVersion((v) => v + 1);
    };
    element.addEventListener("webglcontextlost", lost);
    element.addEventListener("webglcontextrestored", initialize);
    initialize();
    return () => {
      element.removeEventListener("webglcontextlost", lost);
      element.removeEventListener("webglcontextrestored", initialize);
      gpu.current?.dispose();
      gpu.current = null;
    };
  }, [curveRenderer]);
  const typography = usePlotTypography(container);
  const [size, setSize] = useState({ width: 900, height: 230 });
  const [left, setLeft] = useState(76);
  const [axisAnnotation, setAxisAnnotation] = useState(false);
  const navigating = useRef(false);
  const curveCache = useRef<{
    key: unknown[];
    canvas: HTMLCanvasElement;
    renderer: "webgl2" | "canvas2d";
  } | null>(null);
  const regionDrag = useRef<{
    name: string;
    mode: "min" | "max" | "move";
    startPixel: number;
    scale: number;
    min: number;
    max: number;
    bounds?: [number, number];
    minWidth?: number;
    next: { name: string; min: number; max: number } | null;
  } | null>(null);
  const [regionDraft, setRegionDraft] = useState<{
    name: string;
    min: number;
    max: number;
  } | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [hoverY, setHoverY] = useState<number>(0);
  const inspectionId = useId();
  const [keyboardSample, setKeyboardSample] = useState<{
    index: number;
    x: number;
    y: number;
    name: string;
    sourceX: number[];
    sourceY: (number | null)[];
  } | null>(null);
  const inspectedCurve = showPattern
    ? pattern
    : (curves.find((curve) => curve.selected) ?? curves[0]);
  const inspected =
    keyboardSample &&
    keyboardSample.sourceX === inspectedCurve?.x &&
    keyboardSample.sourceY === inspectedCurve?.y
      ? keyboardSample
      : null;
  useEffect(() => {
    setKeyboardSample(null);
  }, [inspectedCurve?.x, inspectedCurve?.y, pattern.unit]);

  const regionKey = JSON.stringify(regions);
  const cancelRegionDrag = (restore = false) => {
    const dragging = !!regionDrag.current;
    regionDrag.current = null;
    setRegionDraft(null);
    if (restore && dragging) onRegionCancel?.();
  };
  useEffect(() => {
    // Responses and optimistic edge positions must not end a live gesture.
    if (!editRegions || !onRegionInput) cancelRegionDrag();
  }, [editRegions, regionKey]);
  useEffect(() => cancelRegionDrag(), [pattern.unit]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && regionDrag.current) {
        event.preventDefault();
        cancelRegionDrag(true);
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [onRegionCancel]);
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
    if (!viewport) navigation.reset();
    setHover(null);
  }, [
    pattern.unit,
    onAutoRange ? null : pattern.x[0],
    onAutoRange ? null : pattern.x.at(-1),
    log,
    sqrt,
  ]);
  // Reserve space for exponents only; legends float inside the data view.
  const right = compact ? 0 : 32,
    top = (compact && !axisAnnotation ? 6 : 18) * typography.scale,
    bottom = (showXAxis ? 52 : 8) * typography.scale;
  const w = Math.max(1, size.width - left - right),
    h = Math.max(1, size.height - top - bottom);
  const visibleCurves = useMemo(
    () => (showPattern ? [pattern, ...curves] : curves),
    [showPattern, pattern, curves],
  );
  const transform = (y: number) =>
    log ? Math.log10(Math.max(1e-6, y)) : sqrt ? Math.sqrt(Math.max(0, y)) : y;
  // Extents do not depend on cursor or view; scan only on data/scale changes.
  const [fitXMin, fitXMax, fitYMin, fitYMax] = useMemo(() => {
    let xmin = Infinity,
      xmax = -Infinity,
      ymin = Infinity,
      ymax = -Infinity;
    for (const curve of visibleCurves) {
      for (const x of curve.x)
        if (Number.isFinite(x)) {
          xmin = Math.min(xmin, x);
          xmax = Math.max(xmax, x);
        }
      for (const y of curve.y)
        if (y !== null && Number.isFinite(y) && (!log || y > 0)) {
          const value = transform(y);
          ymin = Math.min(ymin, value);
          ymax = Math.max(ymax, value);
        }
    }
    const [low, high] = ymin === Infinity ? [0, 1] : paddedExtent([ymin, ymax]);
    return [
      xmin === Infinity ? 0 : xmin,
      xmax === -Infinity ? 1 : xmax,
      low,
      high,
    ];
  }, [visibleCurves, log, sqrt]);
  const horizontalYRange = useCallback(
    (xMin: number, xMax: number): [number, number] => {
      let min = Infinity,
        max = -Infinity;
      for (const curve of visibleCurves) {
        const [start, end] = visibleSamples(curve.x, xMin, xMax, false);
        for (let i = start; i < end; i++) {
          const x = curve.x[i],
            y = curve.y[i];
          if (
            !Number.isFinite(x) ||
            x < xMin ||
            x > xMax ||
            y === null ||
            !Number.isFinite(y) ||
            (log && y <= 0)
          )
            continue;
          const value = transform(y);
          min = Math.min(min, value);
          max = Math.max(max, value);
        }
      }
      return min === Infinity ? [fitYMin, fitYMax] : paddedExtent([min, max]);
    },
    [visibleCurves, log, sqrt, fitYMin, fitYMax],
  );
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
    horizontalYRange,
    viewport,
  );
  const previousAutoRange = useRef<
    { value: boolean; managed: boolean } | undefined
  >(undefined);
  useEffect(() => {
    const previous = previousAutoRange.current;
    const managed = !!onAutoRange;
    const toggled =
      previous?.managed && managed && previous.value !== autoRange;
    previousAutoRange.current = { value: autoRange, managed };
    if (navigating.current || (regionDrag.current && onRegionInput)) return;
    if (viewport) {
      // A mode may mount with a different Auto preference. Adopt the shared
      // viewport unless the user explicitly toggled Auto in this mounted view.
      if (toggled) {
        if (autoRange) navigation.reset();
        else navigation.hold();
      } else onAutoRange?.(!viewport.read());
      return;
    }
    if (autoRange) navigation.reset();
    else if (onAutoRange) navigation.hold();
  }, [pattern, autoRange, showPattern, viewport?.key]);
  usePlotWheel(canvas, (event) => {
    if (keyboardSample) {
      setKeyboardSample(null);
      setHover(null);
    }
    onAutoRange?.(false);
    navigation.onWheel(event);
  });
  const { xMin: xmin, xMax: xmax, yMin: ymin, yMax: ymax } = navigation.view;
  useEffect(() => {
    onViewChange?.({ xMin: xmin, xMax: xmax, yMin: ymin, yMax: ymax });
  }, [xmin, xmax, ymin, ymax, onViewChange]);
  const yspan = ymax - ymin;
  const regionAt = (x: number) => {
    const tolerance = ((xmax - xmin) * 9) / w;
    return [...regions]
      .sort((a, b) => {
        const edge = (r: PatternRegion) =>
          Math.min(Math.abs(x - r.min), Math.abs(x - r.max));
        const ae = edge(a),
          be = edge(b);
        if (ae <= tolerance || be <= tolerance) return ae - be;
        return Number(!!b.active) - Number(!!a.active);
      })
      .find((r) =>
        r.movable === false
          ? Math.min(Math.abs(x - r.min), Math.abs(x - r.max)) <= tolerance
          : x >= r.min - tolerance && x <= r.max + tolerance,
      );
  };
  const updateRegionDrag = (point: { x: number; y: number }) => {
    const drag = regionDrag.current;
    if (!drag) return;
    let dx = (point.x - drag.startPixel) * drag.scale;
    const [lower, upper] = drag.bounds ?? [-Infinity, Infinity];
    const gap = drag.minWidth ?? Number.EPSILON;
    if (drag.mode === "move")
      dx = Math.max(lower - drag.min, Math.min(upper - drag.max, dx));
    const min =
      drag.mode === "max"
        ? drag.min
        : Math.max(
            lower,
            Math.min(
              drag.mode === "min" ? drag.max - gap : Infinity,
              drag.min + dx,
            ),
          );
    const max =
      drag.mode === "min"
        ? drag.max
        : Math.min(
            upper,
            Math.max(
              drag.mode === "max" ? drag.min + gap : -Infinity,
              drag.max + dx,
            ),
          );
    if (min < max) {
      const changed =
        !drag.next || drag.next.min !== min || drag.next.max !== max;
      const moved = !!drag.next || min !== drag.min || max !== drag.max;
      drag.next = { name: drag.name, min, max };
      setRegionDraft(drag.next);
      if (changed && moved) onRegionInput?.(drag.name, min, max);
    }
  };
  const hoveredRegion =
    editRegions && hover !== null
      ? regionAt(xmin + ((hover - left) / w) * (xmax - xmin))
      : undefined;
  const regionCursor = regionDrag.current
    ? regionDrag.current.mode === "move"
      ? "grabbing"
      : "ew-resize"
    : hoveredRegion
      ? Math.min(
          Math.abs(
            hover! - (left + ((hoveredRegion.min - xmin) / (xmax - xmin)) * w),
          ),
          Math.abs(
            hover! - (left + ((hoveredRegion.max - xmin) / (xmax - xmin)) * w),
          ),
        ) < 9
        ? "ew-resize"
        : "grab"
      : undefined;
  // Submit the pattern in the same commit as the detector, before WebKit paints.
  const renderPattern = (exporting = false) => {
    const started = performance.now();
    const back = exporting
      ? document.createElement("canvas")
      : backdrop.current;
    const front = exporting ? document.createElement("canvas") : canvas.current;
    if (!back || !front) throw Error("The pattern has not been rendered yet.");
    const backRecording = exporting ? new SvgRecording(back) : null;
    const frontRecording = exporting ? new SvgRecording(front) : null;
    const cache = exporting
      ? { current: null as typeof curveCache.current }
      : curveCache;
    const backgroundContext = backRecording?.context ?? back.getContext("2d");
    if (!backgroundContext) throw Error("Plot drawing is unavailable.");
    let context: CanvasRenderingContext2D = backgroundContext;
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(size.width * dpr));
    const height = Math.max(1, Math.round(size.height * dpr));
    if (back.width !== width) back.width = width;
    if (back.height !== height) back.height = height;
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, width, height);
    context.scale(dpr, dpr);
    context.lineWidth = 1;
    context.setLineDash([]);
    context.font = typography.mono;
    // Tick density must not depend on the annotation it creates. At compact
    // heights, changing the top gutter can otherwise toggle the annotation
    // and synchronously redraw forever.
    const tickHeight = Math.max(
      1,
      size.height - 18 * typography.scale - bottom,
    );
    const intervalsY = Math.max(
      1,
      Math.floor(tickHeight / (48 * typography.scale)),
    );
    const inverse = (v: number) => Math.max(0, v) ** 2;
    const yAxis = log
      ? { ticks: logTicks(ymin, ymax, intervalsY), annotation: null }
      : linearAxisTicks(
          sqrt ? inverse(ymin) : ymin,
          sqrt ? inverse(ymax) : ymax,
          intervalsY,
        );
    if (!exporting && axisAnnotation !== !!yAxis.annotation)
      setAxisAnnotation(!!yAxis.annotation);
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
    const nextLeft = axisLeft ?? Math.max(64, Math.ceil(tickWidth) + 44);
    if (!exporting && nextLeft !== left) setLeft(nextLeft);
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
      context.fillStyle = typography.muted;
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
      if (!showXAxis) continue;
      context.strokeStyle = "#65717d";
      context.beginPath();
      context.moveTo(x, top + h);
      context.lineTo(x, top + h + 4);
      context.stroke();
      context.fillStyle = typography.muted;
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
      context.fillStyle = typography.muted;
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
      const range = region.appearance === "range";
      const drag =
        regionDrag.current?.name === region.name ? regionDrag.current : null;
      const hovered = hoveredRegion?.name === region.name;
      if (range) {
        const activeEdge = drag
          ? drag.mode === "move"
            ? undefined
            : drag.mode
          : hovered &&
              hover !== null &&
              Math.min(Math.abs(hover - x0), Math.abs(hover - x1)) < 9
            ? Math.abs(hover - x0) <= Math.abs(hover - x1)
              ? "min"
              : "max"
            : undefined;
        drawRangeSelection(
          context,
          x0,
          x1,
          top,
          h,
          region.color,
          activeEdge,
          drag?.mode === "move" || (hovered && regionCursor === "grab"),
        );
      } else {
        context.fillStyle =
          region.color + (hovered || drag ? "55" : region.active ? "2d" : "22");
        context.fillRect(x0, top, x1 - x0, h);
        context.strokeStyle = region.color;
        context.lineWidth = region.active ? 2 : 1;
        context.strokeRect(x0, top, x1 - x0, h);
      }
      context.fillStyle = region.color;
      context.textAlign = "left";
      context.fillText(region.name, x0 + 5, top + 14);
    }
    context.restore();
    const backdropFont = context.font;
    context = frontRecording?.context ?? front.getContext("2d")!;
    if (front.width !== width) front.width = width;
    if (front.height !== height) front.height = height;
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, width, height);
    context.scale(dpr, dpr);
    context.font = backdropFont;
    context.lineWidth = 1;
    context.setLineDash([]);
    context.save();
    context.beginPath();
    context.rect(left, top, w, h);
    context.clip();
    // Reuse curve pixels when only the cursor, selection or editable region changes.
    const curveKey = [
      typography.muted,
      typography.mono,
      gpuVersion,
      curveRenderer,
      pattern,
      showPattern,
      emphasizePattern,
      patternColor,
      log,
      sqrt,
      antialias,
      width,
      height,
      dpr,
      left,
      top,
      w,
      h,
      xmin,
      xmax,
      ymin,
      ymax,
      curves,
      referenceLines,
      referenceMode,
      calibrantLines,
      activeRing,
      showNumbers,
    ];
    if (
      !cache.current ||
      curveKey.some((v, i) => !Object.is(v, cache.current!.key[i]))
    ) {
      const layer = cache.current?.canvas ?? document.createElement("canvas");
      layer.dataset.testid = "pattern-curves";
      if (layer.width !== width) layer.width = width;
      if (layer.height !== height) layer.height = height;
      const curveRecording = exporting ? new SvgRecording(layer) : null;
      const curveContext = curveRecording?.context ?? layer.getContext("2d")!;
      curveContext.setTransform(1, 0, 0, 1, 0, 0);
      curveContext.clearRect(0, 0, width, height);
      curveContext.scale(dpr, dpr);
      curveContext.font = context.font;
      curveContext.save();
      curveContext.beginPath();
      curveContext.rect(left, top, w, h);
      curveContext.clip();
      const drawCurve = (
        curve: { x: number[]; y: (number | null)[] },
        color: string,
        width: number,
      ) => {
        if (curveRecording) curveRecording.crispEdges = !antialias;
        curveContext.strokeStyle = color;
        curveContext.fillStyle = color;
        curveContext.lineWidth = width;
        const pixelWidth = width > 2 ? Math.round(width) : 1;
        curveContext.beginPath();
        let previous: [number, number] | null = null;
        const [startIndex, endIndex] = visibleSamples(curve.x, xmin, xmax);
        for (let i = startIndex; i < endIndex; i++) {
          const x = curve.x[i],
            y = curve.y[i];
          if (
            !Number.isFinite(x) ||
            y == null ||
            !Number.isFinite(y) ||
            (log && y <= 0)
          ) {
            previous = null;
            continue;
          }
          const point: [number, number] = [
            left + ((x - xmin) / (xmax - xmin)) * w,
            top + h - ((transform(y) - ymin) / yspan) * h,
          ];
          if (antialias || exporting) {
            if (previous) curveContext.lineTo(...point);
            else curveContext.moveTo(...point);
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
                curveContext.fillRect(
                  Math.floor(previous[0] + dx * t - (pixelWidth - 1) / 2),
                  Math.floor(previous[1] + dy * t - (pixelWidth - 1) / 2),
                  pixelWidth,
                  pixelWidth,
                );
              }
            }
          }
          previous = point;
        }
        if (antialias || exporting) curveContext.stroke();
        if (curveRecording) curveRecording.crispEdges = false;
      };
      let usingGPU = false;
      if (
        !exporting &&
        curveRenderer === "webgl2" &&
        gpu.current &&
        antialias
      ) {
        const ordered: PatternCurve[] = [];
        if (showPattern && !emphasizePattern)
          ordered.push({ ...pattern, color: patternColor, width: 1.4 });
        for (const curve of curves.filter((c) => !c.selected))
          ordered.push({ ...curve, width: 1.2 });
        for (const curve of curves.filter((c) => c.selected))
          ordered.push({ ...curve, width: 2.4 });
        if (showPattern && emphasizePattern)
          ordered.push({ ...pattern, color: patternColor, width: 2.4 });
        try {
          const frame: PatternFrame = {
            curves: ordered,
            scale: log ? "log" : sqrt ? "sqrt" : "linear",
            view: { xMin: xmin, xMax: xmax, yMin: ymin, yMax: ymax },
            bounds: { left, top, width: w, height: h },
            size: { ...size, dpr },
          };
          gpu.current.draw(frame);
          gpuFrame.current = frame;
          usingGPU = true;
        } catch {
          usingGPU = false;
        }
      }
      if (!exporting) setActiveRenderer(usingGPU ? "webgl2" : "canvas2d");
      if (!usingGPU) {
        if (showPattern && !emphasizePattern)
          drawCurve(pattern, patternColor, 1.4);
        // Measured curves and background inspection share the same axes and drawing mode.
        // Draw the selected overlay last so it remains identifiable where curves overlap.
        for (const curve of curves.filter((curve) => !curve.selected))
          drawCurve(curve, curve.color, 1.2);
        for (const curve of curves.filter((curve) => curve.selected))
          drawCurve(curve, curve.color, 2.4);
        if (showPattern && emphasizePattern)
          drawCurve(pattern, patternColor, 2.4);
      }
      const phaseLineTops = scalePhaseLines(
        pattern,
        referenceLines,
        navigation.view,
        (y) => (log && y <= 0 ? NaN : transform(y)),
      );
      for (const [index, line] of referenceLines.entries()) {
        const x = left + ((line.x - xmin) / (xmax - xmin)) * w;
        if (x < left || x > left + w) continue;
        curveContext.strokeStyle = line.color;
        curveContext.lineWidth = 1.3;
        curveContext.beginPath();
        curveContext.moveTo(x, top + h);
        curveContext.lineTo(
          x,
          referenceMode === "full-height"
            ? top
            : top + h - ((phaseLineTops[index] - ymin) / yspan) * h,
        );
        curveContext.stroke();
      }
      const ringLabelBoxes: { left: number; right: number; row: number }[] = [];
      for (const reference of calibrantLines) {
        const x = left + ((reference.x - xmin) / (xmax - xmin)) * w;
        if (x < left || x > left + w) continue;
        const active = reference.ring === activeRing;
        curveContext.strokeStyle = active ? "#ff4040d9" : "#ff4040b3";
        curveContext.lineWidth = active ? 2.2 : 1;
        curveContext.beginPath();
        curveContext.moveTo(x, top);
        curveContext.lineTo(x, top + h);
        curveContext.stroke();
        if (showNumbers) {
          curveContext.fillStyle = "#ff4040";
          const text = String(reference.ring),
            width = curveContext.measureText(text).width;
          const labelX = Math.max(
            left + 2,
            Math.min(x + 4, left + w - width - 2),
          );
          const row = Array.from({ length: 4 }, (_, i) => i).find(
            (row) =>
              !ringLabelBoxes.some(
                (box) =>
                  box.row === row &&
                  labelX < box.right + 5 &&
                  labelX + width > box.left - 5,
              ),
          );
          if (row !== undefined) {
            ringLabelBoxes.push({ left: labelX, right: labelX + width, row });
            curveContext.fillText(text, labelX, top + 14 + row * 16);
          }
        }
      }
      curveContext.restore();
      cache.current = {
        key: curveKey,
        canvas: layer,
        renderer: usingGPU ? "webgl2" : "canvas2d",
      };
    }
    context.drawImage(cache.current.canvas, 0, 0, width / dpr, height / dpr);
    if (navigation.selection) {
      const { start, end } = navigation.selection;
      const x = Math.min(start.x, end.x),
        y = Math.min(start.y, end.y);
      const width = Math.abs(end.x - start.x),
        height = Math.abs(end.y - start.y);
      if (zoomMode === "horizontal") {
        drawRangeSelection(
          context,
          x,
          x + width,
          y,
          height,
          RANGE_SELECTION_COLOR,
        );
      } else {
        context.fillStyle = RANGE_SELECTION_COLOR + "20";
        context.strokeStyle = RANGE_SELECTION_COLOR;
        context.fillRect(x, y, width, height);
        context.strokeRect(x, y, width, height);
      }
    }
    if (hover !== null) {
      // Match the linked click marker so overlapping guides share one rhythm.
      context.lineWidth = 1.5;
      context.setLineDash([6, 3]);
      context.strokeStyle = "#7a8c9c";
      context.beginPath();
      context.moveTo(hover, top);
      context.lineTo(hover, top + h);
      context.stroke();
    }
    // Keep the clicked position in front when the moving guide overlaps it.
    if (linkedPosition !== undefined) {
      const x = left + ((linkedPosition - xmin) / (xmax - xmin)) * w;
      context.strokeStyle = POSITION_LINE_COLOR;
      context.lineWidth = 1.5;
      // Qt DashLine uses four pen widths on, two off.
      context.setLineDash([6, 3]);
      context.beginPath();
      context.moveTo(x, top);
      context.lineTo(x, top + h);
      context.stroke();
      context.setLineDash([]);
    }
    context.restore();
    context.fillStyle = typography.muted;
    context.textAlign = "center";
    if (showXAxis)
      context.fillText(unitLabel(pattern.unit), left + w / 2, size.height - 8);
    context.save();
    context.translate(16, top + h / 2);
    context.rotate(-Math.PI / 2);
    context.textBaseline = "middle";
    context.fillText(yLabel, 0, 0);
    context.restore();
    if (exporting) {
      const output = document.createElement("canvas");
      output.width = width;
      output.height = height;
      const recording = new SvgRecording(output);
      const result = recording.context;
      // Paint the actual workspace background once; all curve layers stay transparent.
      result.fillStyle =
        getComputedStyle(container.current!)
          .getPropertyValue("--ui-workspace")
          .trim() || "#101518";
      result.fillRect(0, 0, width, height);
      result.drawImage(back, 0, 0);
      result.drawImage(front, 0, 0);
      result.scale(dpr, dpr);
      drawFigureLegends(result, container.current!);
      const svg = recording.svg(size.width, size.height);
      // PNG uses the actual current renderer's layers, including GPU line AA.
      // WebGL discards its drawing buffer after presentation, so repaint the
      // identical retained frame immediately before compositing it.
      const pixels = output.getContext("2d")!;
      let useDisplayedLayers = false;
      let gpuPixels: HTMLCanvasElement | null = null;
      if (
        curveCache.current?.renderer === "webgl2" &&
        gpu.current &&
        gpuFrame.current
      ) {
        try {
          gpu.current.draw(gpuFrame.current);
          gpuPixels = gpuCanvas.current;
          useDisplayedLayers = true;
        } catch {
          /* Context loss retains the complete Canvas export above. */
        }
      } else if (curveCache.current?.renderer === "canvas2d") {
        useDisplayedLayers = true;
      }
      if (useDisplayedLayers && backdrop.current && canvas.current) {
        pixels.setTransform(1, 0, 0, 1, 0, 0);
        pixels.fillStyle =
          getComputedStyle(container.current!)
            .getPropertyValue("--ui-workspace")
            .trim() || "#101518";
        pixels.fillRect(0, 0, width, height);
        pixels.drawImage(backdrop.current, 0, 0);
        if (gpuPixels) pixels.drawImage(gpuPixels, 0, 0);
        pixels.drawImage(canvas.current, 0, 0);
        pixels.scale(dpr, dpr);
        drawFigureLegends(pixels, container.current!);
      }
      return {
        png_data: output.toDataURL("image/png").split(",")[1],
        svg_data: svg,
      };
    }
    navigationTrace("pattern-rendered", {
      cpuMs: performance.now() - started,
      renderer: cache.current.renderer,
    });
    renderObserver.current?.({
      cpuMs: performance.now() - started,
      renderer: cache.current.renderer,
      xMin: xmin,
      xMax: xmax,
      uploads: gpu.current?.stats.uploads,
      uploadBytes: gpu.current?.stats.uploadBytes,
    });
  };
  useLayoutEffect(() => {
    renderPattern();
    exportDraw.current = () => renderPattern(true)!;
    return () => {
      exportDraw.current = null;
    };
  }, [
    yLabel,
    showXAxis,
    axisLeft,
    referenceMode,
    typography.muted,
    typography.mono,
    gpuVersion,
    curveRenderer,
    pattern,
    showPattern,
    emphasizePattern,
    patternColor,
    log,
    sqrt,
    antialias,
    size,
    hover,
    xmin,
    xmax,
    ymin,
    ymax,
    navigation.selection,
    zoomMode,
    linkedPosition,
    activeRing,
    calibrantLines,
    showNumbers,
    curves,
    referenceLines,
    regions,
    editRegions,
    regionDraft,
    left,
    top,
    right,
  ]);
  // Metadata snapshots follow labels/views without adding redraw dependencies.
  useLayoutEffect(() => {
    if (!exportRef) return;
    figureSource.current = {
      curves: [
        ...(showPattern
          ? [
              {
                id: "measured",
                name: overlayLegend?.[0]?.name || "Measured pattern",
                color: patternColor,
                x: pattern.x,
                y: pattern.y,
              },
            ]
          : []),
        ...curves.map((curve, i) => ({
          ...curve,
          id: `overlay:${i}:${curve.name}`,
        })),
      ],
      phases: referenceLines,
      pattern,
      unit: pattern.unit,
      view: { ...navigation.view },
      scale: log ? "log" : sqrt ? "sqrt" : "linear",
    };
  });
  const inspectByKeyboard = (event: ReactKeyboardEvent<HTMLCanvasElement>) => {
    if (
      !event.altKey ||
      event.metaKey ||
      event.ctrlKey ||
      !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
    )
      return false;
    event.preventDefault();
    event.stopPropagation();
    if (!inspectedCurve) return true;
    const actions: Record<string, InspectionDirection> = {
      ArrowLeft: "previous",
      ArrowRight: "next",
      Home: "first",
      End: "last",
    };
    for (const index of sampleInspectionOrder(
      inspectedCurve.x,
      xmin,
      xmax,
      inspected?.index ?? null,
      actions[event.key],
    )) {
      const x = inspectedCurve.x[index],
        y = inspectedCurve.y[index];
      if (
        !Number.isFinite(x) ||
        y == null ||
        !Number.isFinite(y) ||
        (log && y <= 0)
      )
        continue;
      const transformed = transform(y);
      if (transformed < ymin || transformed > ymax) continue;
      setKeyboardSample({
        index,
        x,
        y,
        name: showPattern
          ? (overlayLegend?.[0]?.name ?? "Original pattern")
          : "name" in inspectedCurve && typeof inspectedCurve.name === "string"
            ? inspectedCurve.name
            : "Overlay",
        sourceX: inspectedCurve.x,
        sourceY: inspectedCurve.y,
      });
      setHover(left + ((x - xmin) / (xmax - xmin)) * w);
      setHoverY(top + h - ((transformed - ymin) / yspan) * h);
      break;
    }
    return true;
  };
  const xvalue =
    hover === null ? null : xmin + ((hover - left) / w) * (xmax - xmin);
  const mouseValue = (y: number) =>
    log ? 10 ** y : sqrt ? Math.max(0, y) ** 2 : y;
  const mouseY = mouseValue(ymax - ((hoverY - top) / h) * (ymax - ymin));
  const xResolution = Math.abs(xmax - xmin) / w;
  const yResolutionAt = (y: number) =>
    Math.abs(
      mouseValue(y + (ymax - ymin) / h / 2) -
        mouseValue(y - (ymax - ymin) / h / 2),
    );
  const yResolution = yResolutionAt(
    ymax - ((hoverY - top) / h) * (ymax - ymin),
  );
  useEffect(() => {
    if (w > 1) onResolution?.(xResolution);
  }, [w, xResolution, onResolution]);
  const nearest = xvalue === null ? -1 : nearestSample(pattern.x, xvalue);
  useEffect(() => {
    onHover?.(
      inspected
        ? {
            x: inspected.x,
            y: inspected.y,
            mouseY: inspected.y,
            xResolution,
            yResolution,
            unit: pattern.unit,
            valueLabel,
            hint: `${inspected.name} · sample ${inspected.index + 1} of ${inspected.sourceX.length}`,
          }
        : nearest >= 0
          ? {
              x: xvalue!,
              y: pattern.y[nearest],
              mouseY,
              xResolution,
              yResolution,
              unit: pattern.unit,
              valueLabel,
              hint: hoverHint,
            }
          : null,
    );
  }, [
    inspected,
    nearest,
    xvalue,
    mouseY,
    xResolution,
    yResolution,
    pattern,
    onHover,
    hoverHint,
    valueLabel,
  ]);
  return (
    <div ref={container} className="pattern-container">
      {referenceMode === "scaled" && (
        <IntegrationPhaseLegend
          lines={referenceLines}
          left={left}
          top={top + 5}
          bounds={{ left, top, width: w, height: h }}
        />
      )}
      <canvas
        ref={backdrop}
        className="pattern-background-layer"
        data-testid="pattern-axes"
        aria-hidden="true"
      />
      <canvas
        ref={gpuCanvas}
        key={curveRenderer}
        className="pattern-gpu-layer"
        data-testid="pattern-gpu"
        aria-hidden="true"
        style={{
          visibility: activeRenderer === "webgl2" ? "visible" : "hidden",
        }}
      />
      <canvas
        ref={canvas}
        tabIndex={0}
        onKeyDown={(event) => {
          if (inspectByKeyboard(event)) return;
          if (
            [
              "ArrowLeft",
              "ArrowRight",
              "ArrowUp",
              "ArrowDown",
              "Home",
              "f",
              "F",
              "+",
              "-",
              "=",
            ].includes(event.key) &&
            keyboardSample
          ) {
            setKeyboardSample(null);
            setHover(null);
          }
          navigation.onKeyDown(event);
        }}
        onBlur={() => {
          if (keyboardSample) {
            setKeyboardSample(null);
            setHover(null);
          }
        }}
        aria-describedby={inspectionId}
        aria-description="Alt+Left or Right inspects plotted samples without changing the view. Alt+Home or End selects the first or last visible sample."
        data-keyboard-sample={inspected?.index}
        data-keyboard-x={inspected?.x}
        data-keyboard-y={inspected?.y}
        data-testid="pattern-canvas"
        data-curve-renderer={activeRenderer}
        data-requested-curve-renderer={curveRenderer}
        aria-label={`${plotLabel}; left-drag ${zoomMode} zoom, right-drag pan, right-click zoom out; keyboard arrows pan, +/- zoom, F restores view`}
        style={{ width: "100%", height: "100%", cursor: regionCursor }}
        data-regions={JSON.stringify(
          regions.map((r) =>
            regionDraft?.name === r.name ? { ...r, ...regionDraft } : r,
          ),
        )}
        data-edit-regions={editRegions}
        data-region-updating={regionsUpdating}
        data-show-x-axis={showXAxis}
        data-intensity-scale={log ? "log" : sqrt ? "sqrt" : "linear"}
        data-plot-font-size={typography.size}
        data-antialias={antialias}
        data-auto-range={autoRange}
        data-curve-count={curves.length}
        data-original-visible={showPattern}
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
            !isPlotSecondaryGesture(e) &&
            onRegionChange &&
            point.x >= left &&
            point.x <= left + w &&
            point.y >= top &&
            point.y <= top + h
          ) {
            const x = navigation.data(point).x;
            const tolerance = ((xmax - xmin) * 9) / w;
            const region = regionAt(x);
            if (region) {
              regionDrag.current = {
                name: region.name,
                startPixel: point.x,
                scale: (xmax - xmin) / w,
                min: region.min,
                max: region.max,
                bounds: region.bounds,
                minWidth: region.minWidth,
                next: null,
                mode:
                  Math.min(Math.abs(x - region.min), Math.abs(x - region.max)) <
                  tolerance
                    ? Math.abs(x - region.min) <= Math.abs(x - region.max)
                      ? "min"
                      : "max"
                    : "move",
              };
              onRegionDragStart?.();
              e.currentTarget.focus({ preventScroll: true });
              if (onRegionInput) navigation.hold();
              e.preventDefault();
              e.currentTarget.setPointerCapture(e.pointerId);
              return;
            }
          }
          navigating.current = navigation.onPointerDown(
            e,
            true,
            zoomMode === "rectangle",
          );
        }}
        onPointerMove={(e) => {
          if (keyboardSample) setKeyboardSample(null);
          const drag = regionDrag.current;
          if (drag) {
            updateRegionDrag(navigation.screen(e));
            return;
          }
          const point = navigation.screen(e);
          setHover(
            point.x >= left &&
              point.x <= left + w &&
              point.y >= top &&
              point.y <= top + h
              ? point.x
              : null,
          );
          setHoverY(point.y);
          navigation.onPointerMove(e);
        }}
        onPointerUp={(e) => {
          if (regionDrag.current) {
            updateRegionDrag(navigation.screen(e));
            const { name, next, min, max } = regionDrag.current;
            if (next && (next.min !== min || next.max !== max))
              onRegionChange?.(next.name, next.min, next.max);
            else {
              onRegionSelect?.(name);
              const point = navigation.data(navigation.screen(e));
              onInspect?.(point.x, mouseValue(point.y), {
                x: xResolution,
                y: yResolutionAt(point.y),
              });
            }
            regionDrag.current = null;
            setRegionDraft(null);
            if (e.currentTarget.hasPointerCapture(e.pointerId))
              e.currentTarget.releasePointerCapture(e.pointerId);
            return;
          }
          const result = navigation.onPointerUp(e);
          navigating.current = false;
          if (result === "reset") onAutoRange?.(true);
          if (result === "zoom" || result === "pan" || result === "unzoom")
            onAutoRange?.(false);
          if (result === "click") {
            const point = navigation.data(navigation.screen(e));
            onInspect?.(point.x, mouseValue(point.y), {
              x: xResolution,
              y: yResolutionAt(point.y),
            });
            onPick?.(point.x, mouseValue(point.y), {
              x: xResolution,
              y: yResolutionAt(point.y),
            });
          }
        }}
        onPointerCancel={(e) => {
          navigating.current = false;
          cancelRegionDrag(true);
          navigation.onPointerCancel(e);
        }}
        onLostPointerCapture={() => {
          navigating.current = false;
          cancelRegionDrag(true);
        }}
        onPointerLeave={() => setHover(null)}
      />
      <span
        className="visually-hidden plot-keyboard-reading"
        id={inspectionId}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {inspected
          ? `${inspected.name}, sample ${inspected.index + 1} of ${inspected.sourceX.length}. ${unitLabel(pattern.unit)} ${scientificValue(inspected.x, 8)}. ${valueLabel ?? "Intensity"} ${scientificValue(inspected.y, 8)}${valueLabel ? "" : " a.u."}.`
          : ""}
      </span>
      {overlayLegend && (
        <OverlayPlotLegend
          entries={overlayLegend}
          left={left + w - 8}
          top={top + 5}
          align="right"
          bounds={{ left, top, width: w, height: h }}
          width={w * 0.7}
          height={h * 0.5}
        />
      )}
      {onZoomMode && (
        <PlotZoomControls
          mode={zoomMode}
          onChange={onZoomMode}
          left={left}
          bottom={showXAxis ? bottom : 28 * typography.scale}
          label={
            plotLabel === "Integrated diffraction pattern"
              ? "Pattern"
              : plotLabel
          }
        />
      )}
    </div>
  );
}

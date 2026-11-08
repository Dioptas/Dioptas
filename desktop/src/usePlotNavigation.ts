import { useEffect, useRef, useState, useMemo } from "react";
import type { PointerEvent, KeyboardEvent, RefObject } from "react";
import type { PlotViewport } from "./plotViewport";

/** React wheel listeners are passive. Own the native wheel event so a plot
 * zoom cannot also scroll its containing workspace (including in WKWebView). */
export function usePlotWheel(
  canvas: RefObject<HTMLCanvasElement | null>,
  onWheel: (event: WheelEvent) => void,
) {
  const latest = useRef(onWheel);
  latest.current = onWheel;
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      latest.current(event);
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [canvas]);
}

export interface PlotRange {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}
export interface PlotBounds {
  left: number;
  top: number;
  width: number;
  height: number;
}
export interface ScreenPoint {
  x: number;
  y: number;
}
export interface ZoomSelection {
  start: ScreenPoint;
  end: ScreenPoint;
}
export type ZoomMode = "rectangle" | "horizontal";
type Gesture = {
  button: "left" | "right";
  start: ScreenPoint;
  last: ScreenPoint;
  range: PlotRange;
  moved: boolean;
};

/** Ctrl/Command + primary button also works with a single-button mouse. */
export function isPlotSecondaryGesture(event: {
  button: number;
  ctrlKey: boolean;
  metaKey: boolean;
}) {
  return (
    event.button === 2 ||
    (event.button === 0 && (event.ctrlKey || event.metaKey))
  );
}

/** Dioptas plot gestures, shared by detector, cake, and diffraction pattern.
 * A right click zooms out once; a right double-click restores the fitted view.
 * Ctrl/Command + left click/drag provides the same navigation.
 */
export function usePlotNavigation(
  fit: PlotRange,
  bounds: PlotBounds,
  aspectLocked = false,
  zoomMode: ZoomMode = "rectangle",
  horizontalYRange?: (xMin: number, xMax: number) => [number, number],
  viewport?: PlotViewport,
) {
  const [localRange, setLocalRange] = useState<PlotRange | null>(null);
  const range = viewport ? viewport.read() : localRange;
  const setRange = (next: PlotRange | null) => {
    viewport?.write(next);
    setLocalRange(next);
  };
  const [selection, setSelection] = useState<ZoomSelection | null>(null);
  const gesture = useRef<Gesture | null>(null);
  const rightClick = useRef<{ time: number; point: ScreenPoint } | null>(null);
  const currentRange = range ?? fit;
  // Slice mode always follows the visible content, including when data changes
  // or the user switches from a manually scaled rectangle view.
  const horizontalExtent = useMemo(
    () =>
      zoomMode === "horizontal" && !aspectLocked
        ? horizontalYRange?.(currentRange.xMin, currentRange.xMax)
        : undefined,
    [
      zoomMode,
      aspectLocked,
      horizontalYRange,
      currentRange.xMin,
      currentRange.xMax,
    ],
  );
  // A zoomed range outlives the viewport that created it. Derive its height
  // from the current canvas aspect on every render, including resize frames.
  const halfHeight =
    ((currentRange.xMax - currentRange.xMin) * bounds.height) /
    Math.max(1, bounds.width) /
    2;
  const centerY = (currentRange.yMin + currentRange.yMax) / 2;
  const view = aspectLocked
    ? {
        ...currentRange,
        yMin: centerY - halfHeight,
        yMax: centerY + halfHeight,
      }
    : horizontalExtent
      ? {
          ...currentRange,
          yMin: horizontalExtent[0],
          yMax: horizontalExtent[1],
        }
      : currentRange;
  const reset = () => {
    gesture.current = null;
    rightClick.current = null;
    setSelection(null);
    setRange(null);
  };
  function screen(
    event: PointerEvent<HTMLCanvasElement> | WheelEvent,
  ): ScreenPoint {
    const box = (
      event.currentTarget as HTMLCanvasElement
    ).getBoundingClientRect();
    return { x: event.clientX - box.left, y: event.clientY - box.top };
  }
  const inside = (p: ScreenPoint) =>
    p.x >= bounds.left &&
    p.x <= bounds.left + bounds.width &&
    p.y >= bounds.top &&
    p.y <= bounds.top + bounds.height;
  const clamp = (p: ScreenPoint): ScreenPoint => ({
    x: Math.max(bounds.left, Math.min(bounds.left + bounds.width, p.x)),
    y: Math.max(bounds.top, Math.min(bounds.top + bounds.height, p.y)),
  });
  function data(p: ScreenPoint, current = view): ScreenPoint {
    return {
      x:
        current.xMin +
        ((p.x - bounds.left) / bounds.width) * (current.xMax - current.xMin),
      y:
        current.yMax -
        ((p.y - bounds.top) / bounds.height) * (current.yMax - current.yMin),
    };
  }
  function scaled(
    current: PlotRange,
    factor: number,
    anchor?: ScreenPoint,
  ): PlotRange | null {
    const width = current.xMax - current.xMin,
      height = current.yMax - current.yMin;
    const fitWidth = fit.xMax - fit.xMin,
      fitHeight = fit.yMax - fit.yMin;
    const center = anchor ?? {
      x: (current.xMin + current.xMax) / 2,
      y: (current.yMin + current.yMax) / 2,
    };
    if (zoomMode === "horizontal" && !aspectLocked) {
      const fullWidth = factor > 1 && width * factor >= fitWidth * (1 - 1e-10);
      const xMin = fullWidth
        ? fit.xMin
        : center.x + (current.xMin - center.x) * factor;
      const xMax = fullWidth
        ? fit.xMax
        : center.x + (current.xMax - center.x) * factor;
      const [yMin, yMax] = horizontalYRange?.(xMin, xMax) ?? [
        current.yMin,
        current.yMax,
      ];
      return { xMin, xMax, yMin, yMax };
    }
    if (
      factor > 1 &&
      width * factor >= fitWidth * (1 - 1e-10) &&
      height * factor >= fitHeight * (1 - 1e-10)
    )
      return null;
    return {
      xMin: center.x + (current.xMin - center.x) * factor,
      xMax: center.x + (current.xMax - center.x) * factor,
      yMin: center.y + (current.yMin - center.y) * factor,
      yMax: center.y + (current.yMax - center.y) * factor,
    };
  }
  function onPointerDown(
    event: PointerEvent<HTMLCanvasElement>,
    allowLeft = true,
    allowMarginSelection = false,
  ) {
    const right = isPlotSecondaryGesture(event);
    const p = screen(event);
    if (!right) rightClick.current = null;
    if (
      (!right && (event.button !== 0 || !allowLeft)) ||
      (!inside(p) && (right || !allowMarginSelection))
    )
      return false;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    gesture.current = {
      button: right ? "right" : "left",
      start: p,
      last: p,
      range: view,
      moved: false,
    };
    return true;
  }
  function onPointerMove(event: PointerEvent<HTMLCanvasElement>) {
    const current = gesture.current;
    if (!current) return;
    const p = screen(event);
    current.last = p;
    if (Math.hypot(p.x - current.start.x, p.y - current.start.y) > 4)
      current.moved = true;
    if (!current.moved) return;
    if (current.button === "right") {
      const dx =
        ((p.x - current.start.x) / bounds.width) *
        (current.range.xMax - current.range.xMin);
      const dy =
        zoomMode === "horizontal" && !aspectLocked
          ? 0
          : ((p.y - current.start.y) / bounds.height) *
            (current.range.yMax - current.range.yMin);
      const xMin = current.range.xMin - dx,
        xMax = current.range.xMax - dx;
      const [yMin, yMax] =
        zoomMode === "horizontal" && !aspectLocked && horizontalYRange
          ? horizontalYRange(xMin, xMax)
          : [current.range.yMin + dy, current.range.yMax + dy];
      setRange({
        xMin,
        xMax,
        yMin,
        yMax,
      });
    } else {
      // Margin-enabled drags may start on the axes. Select the intersection with
      // the plot, keeping gestures that stay in the margins inert.
      const start = clamp(current.start),
        end = clamp(p);
      setSelection(
        Math.abs(end.x - start.x) < 4 ||
          (zoomMode === "rectangle" && Math.abs(end.y - start.y) < 4)
          ? null
          : zoomMode === "horizontal"
            ? {
                start: { x: start.x, y: bounds.top },
                end: { x: end.x, y: bounds.top + bounds.height },
              }
            : { start, end },
      );
    }
  }
  function onPointerUp(event: PointerEvent<HTMLCanvasElement>) {
    const current = gesture.current;
    if (!current) return null;
    gesture.current = null;
    setSelection(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
    if (current.button === "right") {
      if (!current.moved) {
        const previous = rightClick.current;
        const point = screen(event);
        if (
          previous &&
          event.timeStamp - previous.time <= 450 &&
          Math.hypot(point.x - previous.point.x, point.y - previous.point.y) <=
            6
        ) {
          reset();
          return "reset";
        } else {
          rightClick.current = { time: event.timeStamp, point };
          setRange(scaled(view, 2));
        }
      } else rightClick.current = null;
      return current.moved ? "pan" : "unzoom";
    }
    if (!current.moved) return inside(current.start) ? "click" : null;
    const start = clamp(current.start),
      end = clamp(screen(event));
    if (
      Math.abs(end.x - start.x) < 4 ||
      (zoomMode === "rectangle" && Math.abs(end.y - start.y) < 4)
    )
      return "drag";
    const a = data(start, current.range),
      b = data(end, current.range);
    if (zoomMode === "horizontal") {
      const xMin = Math.min(a.x, b.x),
        xMax = Math.max(a.x, b.x);
      let [yMin, yMax] = horizontalYRange?.(xMin, xMax) ?? [
        current.range.yMin,
        current.range.yMax,
      ];
      if (aspectLocked) {
        // Detector pixels remain square even when selecting an x interval.
        const halfHeight =
          ((xMax - xMin) * (fit.yMax - fit.yMin)) / (fit.xMax - fit.xMin) / 2;
        const center = (current.range.yMin + current.range.yMax) / 2;
        yMin = center - halfHeight;
        yMax = center + halfHeight;
      }
      setRange({ xMin, xMax, yMin, yMax });
      return "zoom";
    }
    let width = Math.abs(a.x - b.x),
      height = Math.abs(a.y - b.y);
    if (aspectLocked) {
      const ratio = (fit.xMax - fit.xMin) / (fit.yMax - fit.yMin);
      width = Math.max(width, height * ratio);
      height = width / ratio;
    }
    const cx = (a.x + b.x) / 2,
      cy = (a.y + b.y) / 2;
    setRange({
      xMin: cx - width / 2,
      xMax: cx + width / 2,
      yMin: cy - height / 2,
      yMax: cy + height / 2,
    });
    return "zoom";
  }
  function onPointerCancel(event: PointerEvent<HTMLCanvasElement>) {
    gesture.current = null;
    rightClick.current = null;
    setSelection(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
  }
  function onWheel(event: WheelEvent) {
    rightClick.current = null;
    const p = screen(event);
    if (!inside(p)) return;
    const current = view;
    const factor = Math.exp(Math.max(-2, Math.min(2, event.deltaY * 0.0015)));
    const maxZoom = (fit.xMax - fit.xMin) / (current.xMax - current.xMin);
    if (factor < 1 && maxZoom / factor > 1000) return;
    setRange(scaled(current, factor, data(p, current)));
  }
  function onKeyDown(event: KeyboardEvent<HTMLCanvasElement>) {
    if (event.altKey || event.metaKey || event.ctrlKey) return;
    const key = event.key.toLowerCase();
    if (
      ![
        "+",
        "=",
        "-",
        "f",
        "home",
        "arrowleft",
        "arrowright",
        "arrowup",
        "arrowdown",
      ].includes(key)
    )
      return;
    event.preventDefault();
    event.stopPropagation();
    if (key === "f" || key === "home") {
      reset();
      return;
    }
    if (["+", "=", "-"].includes(key)) {
      const factor = key === "-" ? 2 : 0.5;
      if (factor < 1 && (fit.xMax - fit.xMin) / (view.xMax - view.xMin) >= 1000)
        return;
      setRange(scaled(view, factor));
      return;
    }
    const dx =
      (view.xMax - view.xMin) *
      0.1 *
      (key === "arrowleft" ? -1 : key === "arrowright" ? 1 : 0);
    const dy =
      (view.yMax - view.yMin) *
      0.1 *
      (key === "arrowdown" ? -1 : key === "arrowup" ? 1 : 0);
    const xMin = view.xMin + dx,
      xMax = view.xMax + dx;
    const [yMin, yMax] =
      zoomMode === "horizontal" && dx && horizontalYRange
        ? horizontalYRange(xMin, xMax)
        : [view.yMin + dy, view.yMax + dy];
    setRange({ xMin, xMax, yMin, yMax });
  }
  return {
    view,
    hold: () => setRange(view),
    selection,
    reset,
    screen,
    data,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onPointerCancel,
    onWheel,
    onKeyDown,
  };
}

import {
  useEffect,
  useRef,
  useState,
  type PointerEvent,
  type KeyboardEvent,
  type RefObject,
} from "react";
import { isPlotSecondaryGesture } from "./usePlotNavigation";
import type { CakeProfileEditor } from "./CakeProfileWorkspace";

/** Preview geometry only; native extraction remains the owner of profile values. */
export function previewProfileWindow(
  center: number,
  bins: number,
  columns: number,
): [number, number] {
  if (bins === 1) {
    const column = Math.min(
      columns - 1,
      Math.floor(center + 64 * Number.EPSILON * Math.max(columns, bins, 1)),
    );
    return [column, column + 1];
  }
  return [center - bins / 2, center + bins / 2];
}

type Edge = "min" | "max";
type Projection = {
  ox: number;
  sx: number;
  left: number;
  top: number;
  width: number;
  height: number;
  columns: number;
};
export function useCakeProfileResize(
  canvas: RefObject<HTMLCanvasElement | null>,
  range: [number, number] | null,
  editor: RefObject<CakeProfileEditor | null> | undefined,
  projection: Projection,
) {
  const [edge, setEdge] = useState<Edge | null>(null);
  const gesture = useRef<{
    pointerId: number;
    edge: Edge;
    startX: number;
    startY: number;
    bins: number;
    next: number;
    moved: boolean;
    editor: CakeProfileEditor;
    sx: number;
  } | null>(null);
  const release = () => {
    const g = gesture.current;
    gesture.current = null;
    setEdge(null);
    if (g && canvas.current?.hasPointerCapture(g.pointerId))
      canvas.current.releasePointerCapture(g.pointerId);
  };
  useEffect(
    () => () => {
      const g = gesture.current;
      gesture.current = null;
      if (g && canvas.current?.hasPointerCapture(g.pointerId))
        canvas.current.releasePointerCapture(g.pointerId);
    },
    [canvas],
  );
  const hit = (event: PointerEvent<HTMLCanvasElement>): Edge | null => {
    if (!range || !editor?.current?.ready) return null;
    const box = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - box.left,
      y = event.clientY - box.top;
    const p = projection;
    if (y < p.top || y > p.top + p.height || x < p.left || x > p.left + p.width)
      return null;
    const low = p.ox + Math.max(0, range[0]) * p.sx;
    const high = p.ox + Math.min(p.columns, range[1]) * p.sx;
    const d0 =
      low >= p.left && low <= p.left + p.width ? Math.abs(x - low) : Infinity;
    const d1 =
      high >= p.left && high <= p.left + p.width
        ? Math.abs(x - high)
        : Infinity;
    return Math.min(d0, d1) <= 5 ? (d0 < d1 ? "min" : "max") : null;
  };
  const move = (event: PointerEvent<HTMLCanvasElement>) => {
    const g = gesture.current;
    if (!g || g.pointerId !== event.pointerId) return false;
    event.preventDefault();
    if (Math.hypot(event.clientX - g.startX, event.clientY - g.startY) > 4)
      g.moved = true;
    if (
      !g.moved ||
      !editor?.current?.ready ||
      editor.current.source !== g.editor.source
    )
      return true;
    const bins = Math.max(
      1,
      Math.min(
        1_000_000,
        Math.round(
          g.bins +
            ((g.edge === "max" ? 2 : -2) * (event.clientX - g.startX)) / g.sx,
        ),
      ),
    );
    if (bins !== g.next) {
      g.next = bins;
      editor.current.onBins(bins);
    }
    return true;
  };
  const cancel = () => {
    const g = gesture.current;
    if (!g) return false;
    if (editor?.current?.source === g.editor.source && g.next !== g.bins)
      editor.current.onBins(g.bins);
    release();
    return true;
  };
  return {
    edge,
    get dragging() {
      return gesture.current != null;
    },
    onPointerDown(event: PointerEvent<HTMLCanvasElement>) {
      if (event.button !== 0 || isPlotSecondaryGesture(event)) return false;
      const target = hit(event),
        owner = editor?.current;
      if (!target || !owner) return false;
      event.preventDefault();
      event.stopPropagation();
      event.currentTarget.focus({ preventScroll: true });
      event.currentTarget.setPointerCapture(event.pointerId);
      gesture.current = {
        pointerId: event.pointerId,
        edge: target,
        startX: event.clientX,
        startY: event.clientY,
        bins: owner.bins,
        next: owner.bins,
        moved: false,
        editor: owner,
        sx: projection.sx,
      };
      setEdge(target);
      return true;
    },
    onPointerMove(event: PointerEvent<HTMLCanvasElement>) {
      if (move(event)) return true;
      setEdge(hit(event));
      return false;
    },
    onPointerUp(event: PointerEvent<HTMLCanvasElement>) {
      const g = gesture.current;
      if (!g || g.pointerId !== event.pointerId) return null;
      move(event);
      release();
      return g.moved ? "resize" : "click";
    },
    onPointerCancel: cancel,
    onLostPointerCapture(event: PointerEvent<HTMLCanvasElement>) {
      if (gesture.current?.pointerId === event.pointerId) cancel();
    },
    onPointerLeave() {
      if (!gesture.current) setEdge(null);
    },
    onKeyDown(event: KeyboardEvent<HTMLCanvasElement>) {
      if (!gesture.current) return false;
      event.preventDefault();
      event.stopPropagation();
      if (event.key === "Escape") cancel();
      return true;
    },
  };
}

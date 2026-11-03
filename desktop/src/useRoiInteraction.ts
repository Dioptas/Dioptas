import { useEffect, useRef, useState, type PointerEvent } from "react";

// Scientific rows increase upward; screen rows increase downward.
export type DetectorRoi = [number, number, number, number];
type Point = { x: number; y: number };
type Handle = "nw" | "ne" | "sw" | "se" | "n" | "s" | "w" | "e";
type Target = Handle | "move";
type Projection = { ox: number; yBase: number; sx: number; sy: number };

export function roiHandles(roi: DetectorRoi, p: Projection) {
  const [r0, r1, c0, c1] = roi;
  const left = p.ox + c0 * p.sx,
    right = p.ox + c1 * p.sx;
  const top = p.yBase - r1 * p.sy,
    bottom = p.yBase - r0 * p.sy;
  const cx = (left + right) / 2,
    cy = (top + bottom) / 2;
  return {
    left,
    right,
    top,
    bottom,
    handles: [
      ["nw", left, top],
      ["ne", right, top],
      ["sw", left, bottom],
      ["se", right, bottom],
      ["n", cx, top],
      ["s", cx, bottom],
      ["w", left, cy],
      ["e", right, cy],
    ] as [Handle, number, number][],
  };
}

function hit(roi: DetectorRoi, p: Projection, point: Point): Target | null {
  const b = roiHandles(roi, p),
    tolerance = 7;
  for (const [handle, x, y] of b.handles)
    if (
      Math.abs(point.x - x) <= tolerance &&
      Math.abs(point.y - y) <= tolerance
    )
      return handle;
  if (point.y >= b.top && point.y <= b.bottom) {
    if (Math.abs(point.x - b.left) <= tolerance) return "w";
    if (Math.abs(point.x - b.right) <= tolerance) return "e";
  }
  if (point.x >= b.left && point.x <= b.right) {
    if (Math.abs(point.y - b.top) <= tolerance) return "n";
    if (Math.abs(point.y - b.bottom) <= tolerance) return "s";
  }
  return point.x > b.left &&
    point.x < b.right &&
    point.y > b.top &&
    point.y < b.bottom
    ? "move"
    : null;
}

export function useRoiInteraction({
  roi,
  width,
  height,
  projection,
  busy,
  onChange,
}: {
  roi?: DetectorRoi | null;
  width: number;
  height: number;
  projection: Projection;
  busy?: boolean;
  onChange?: (roi: DetectorRoi) => Promise<void>;
}) {
  const [preview, setPreview] = useState<DetectorRoi | null>(null);
  const gesture = useRef<{
    target: Target;
    start: Point;
    initial: DetectorRoi;
    next: DetectorRoi;
    projection: Projection;
    pointerId: number;
    canvas: HTMLCanvasElement;
  } | null>(null);
  const generation = useRef(0);
  const active = roi ? (preview ?? roi) : null;
  const screen = (event: PointerEvent<HTMLCanvasElement>): Point => {
    const box = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - box.left, y: event.clientY - box.top };
  };
  const release = () => {
    const g = gesture.current;
    gesture.current = null;
    if (g?.canvas.hasPointerCapture(g.pointerId))
      g.canvas.releasePointerCapture(g.pointerId);
  };
  const cancel = () => {
    generation.current++;
    release();
    setPreview(null);
  };
  const key = roi?.join(",");
  useEffect(cancel, [key, width, height, !!onChange]);
  useEffect(() => {
    if (busy && gesture.current) cancel();
  }, [busy]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && gesture.current) {
        event.preventDefault();
        cancel();
      }
    };
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("keydown", escape);
      release();
    };
  }, []);

  function update(event: PointerEvent<HTMLCanvasElement>) {
    const g = gesture.current;
    if (!g || g.pointerId !== event.pointerId) return false;
    const p = screen(event);
    let dx = Math.round((p.x - g.start.x) / g.projection.sx);
    let dy = Math.round((g.start.y - p.y) / g.projection.sy);
    const [r0, r1, c0, c1] = g.initial;
    const next: DetectorRoi = [...g.initial];
    const clamp = (v: number, lo: number, hi: number) =>
      Math.max(lo, Math.min(hi, v));
    if (g.target === "move") {
      dx = clamp(dx, -c0, width - c1);
      dy = clamp(dy, -r0, height - r1);
      next.splice(0, 4, r0 + dy, r1 + dy, c0 + dx, c1 + dx);
    } else {
      if (g.target.includes("w")) next[2] = clamp(c0 + dx, 0, c1 - 1);
      if (g.target.includes("e")) next[3] = clamp(c1 + dx, c0 + 1, width);
      if (g.target.includes("n")) next[1] = clamp(r1 + dy, r0 + 1, height);
      if (g.target.includes("s")) next[0] = clamp(r0 + dy, 0, r1 - 1);
    }
    g.next = next;
    setPreview(next);
    return true;
  }
  return {
    roi: active,
    dragging: !!gesture.current,
    cursor(point: Point | null) {
      if (!active || !onChange || busy || !point) return "crosshair";
      const target = gesture.current?.target ?? hit(active, projection, point);
      if (target === "move") return gesture.current ? "grabbing" : "grab";
      if (target === "w" || target === "e") return "ew-resize";
      if (target === "n" || target === "s") return "ns-resize";
      if (target === "nw" || target === "se") return "nwse-resize";
      if (target === "ne" || target === "sw") return "nesw-resize";
      return "crosshair";
    },
    onPointerDown(event: PointerEvent<HTMLCanvasElement>) {
      if (
        !active ||
        !onChange ||
        busy ||
        event.button !== 0 ||
        event.ctrlKey ||
        gesture.current
      )
        return false;
      const start = screen(event),
        target = hit(active, projection, start);
      if (!target) return false;
      event.preventDefault();
      generation.current++;
      event.currentTarget.setPointerCapture(event.pointerId);
      gesture.current = {
        target,
        start,
        initial: [...active],
        next: [...active],
        projection,
        pointerId: event.pointerId,
        canvas: event.currentTarget,
      };
      setPreview([...active]);
      return true;
    },
    onPointerMove: update,
    onPointerUp(event: PointerEvent<HTMLCanvasElement>) {
      const g = gesture.current;
      if (!g || g.pointerId !== event.pointerId) return false;
      update(event);
      release();
      if (g.next.every((v, i) => v === g.initial[i])) setPreview(null);
      else {
        const epoch = ++generation.current;
        void onChange!(g.next).finally(() => {
          if (generation.current === epoch) setPreview(null);
        });
      }
      return true;
    },
    onLostPointerCapture(event: PointerEvent<HTMLCanvasElement>) {
      if (gesture.current?.pointerId === event.pointerId) cancel();
    },
    onPointerCancel: cancel,
  };
}

import { useLayoutEffect, useRef, useState } from "react";
import "./plotLegend.css";
export type LegendEntry = { name: string; color: string };
export type LegendBounds = {
  left: number;
  top: number;
  width: number;
  height: number;
};
type Point = { x: number; y: number };

/** In-plot legends share bounded positioning; explicit moves survive new data. */
export function PlotLegend({
  label,
  entries,
  left,
  top,
  width,
  height,
  bounds,
  align = "right",
  className = "",
}: {
  label: string;
  entries: LegendEntry[];
  left: number;
  top: number;
  width: number;
  height: number;
  bounds: LegendBounds;
  align?: "left" | "right";
  className?: string;
}) {
  const element = useRef<HTMLDivElement>(null);
  const initialPosition = useRef<Point>({ x: left, y: top });
  const [isManual, setManual] = useState(false);
  const manual = useRef(false),
    positionRef = useRef<Point | null>(null);
  const [position, setPosition] = useState<Point | null>(null);
  const drag = useRef<{
    x: number;
    y: number;
    start: Point;
    started: boolean;
  } | null>(null);
  const initial = (): Point => ({
    x:
      left -
      (align === "right"
        ? (element.current?.getBoundingClientRect().width ?? 0)
        : 0),
    y: top,
  });
  const bounded = (point: Point): Point => {
    const rect = element.current?.getBoundingClientRect();
    if (!rect) return point;
    return {
      x: Math.max(
        bounds.left,
        Math.min(bounds.left + bounds.width - rect.width, point.x),
      ),
      y: Math.max(
        bounds.top,
        Math.min(bounds.top + bounds.height - rect.height, point.y),
      ),
    };
  };
  const commit = (point: Point) => {
    const next = bounded(point);
    const previous = positionRef.current;
    // Refresh/resize effects can run again before React finishes a commit.
    // Bail out before scheduling state, including during React Fast Refresh.
    if (previous?.x === next.x && previous?.y === next.y) return;
    positionRef.current = next;
    setPosition(next);
  };
  const move = (point: Point) => {
    manual.current = true;
    setManual(true);
    commit(point);
  };
  const reset = () => {
    manual.current = false;
    setManual(false);
    initialPosition.current = bounded(initial());
    commit(initialPosition.current);
  };
  useLayoutEffect(() => {
    const node = element.current;
    if (!node) return;
    const refresh = () => {
      initialPosition.current = bounded(initial());
      commit(
        manual.current
          ? (positionRef.current ?? initialPosition.current)
          : initialPosition.current,
      );
    };
    refresh();
    const observer = new ResizeObserver(refresh);
    observer.observe(node);
    return () => observer.disconnect();
  }, [
    left,
    top,
    align,
    bounds.left,
    bounds.top,
    bounds.width,
    bounds.height,
    width,
    height,
    entries.length,
  ]);
  if (!entries.length) return null;
  const start = initialPosition.current;
  const offset =
    manual.current && position
      ? { x: position.x - start.x, y: position.y - start.y }
      : { x: 0, y: 0 };
  return (
    <div
      ref={element}
      className={`plot-legend ${className}`}
      role="group"
      tabIndex={0}
      aria-label={label}
      aria-description={`${isManual ? "Position fixed until reset. " : "Automatically positioned when data or layout changes. "}Drag to move within the plot. Arrow keys move it; Shift moves faster. Home or Escape restores the default. Focus or hover to read long names.`}
      title={`${isManual ? "Position fixed · " : ""}Drag to move · arrow keys move · Home restores · focus for full names`}
      data-manual-position={isManual}
      data-legend-offset={`${offset.x},${offset.y}`}
      style={{
        left: position?.x ?? left,
        top: position?.y ?? top,
        maxWidth: width,
        maxHeight: height,
        textAlign: align,
        transform:
          !position && align === "right" ? "translateX(-100%)" : undefined,
      }}
      onKeyDown={(event) => {
        if (event.ctrlKey || event.altKey || event.metaKey) return;
        const step = event.shiftKey ? 20 : 5;
        const deltas: Record<string, [number, number]> = {
          ArrowLeft: [-step, 0],
          ArrowRight: [step, 0],
          ArrowUp: [0, -step],
          ArrowDown: [0, step],
        };
        if (event.key === "Home" || event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          reset();
        } else if (deltas[event.key]) {
          event.preventDefault();
          event.stopPropagation();
          const [x, y] = deltas[event.key],
            current = positionRef.current ?? initial();
          move({ x: current.x + x, y: current.y + y });
        }
      }}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.focus({ preventScroll: true });
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = {
          x: event.clientX,
          y: event.clientY,
          start: positionRef.current ?? initial(),
          started: false,
        };
      }}
      onPointerMove={(event) => {
        if (drag.current) {
          const distance = Math.hypot(
            event.clientX - drag.current.x,
            event.clientY - drag.current.y,
          );
          if (!drag.current.started && distance < 4) return;
          drag.current.started = true;
          move({
            x: drag.current.start.x + event.clientX - drag.current.x,
            y: drag.current.start.y + event.clientY - drag.current.y,
          });
        }
      }}
      onPointerUp={() => {
        drag.current = null;
      }}
      onPointerCancel={() => {
        drag.current = null;
      }}
      onLostPointerCapture={() => {
        drag.current = null;
      }}
    >
      {entries.map((entry, index) => (
        <div key={index} title={entry.name} style={{ color: entry.color }}>
          {entry.name}
        </div>
      ))}
    </div>
  );
}

import { useLayoutEffect, useRef, useState } from "react";
import "./plotLegend.css";
export type LegendEntry = { name: string; color: string };
export type LegendBounds = {
  left: number;
  top: number;
  width: number;
  height: number;
};

/** Compact phase/curve names share bounded pointer and keyboard positioning. */
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
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; start: typeof offset } | null>(
    null,
  );
  const element = useRef<HTMLDivElement>(null);
  const currentOffset = useRef(offset);
  currentOffset.current = offset;
  const move = (point: typeof offset) => {
    if (!element.current) return;
    const rect = element.current.getBoundingClientRect();
    const minimumX = bounds.left + (align === "right" ? rect.width : 0);
    const maximumX =
      bounds.left + bounds.width - (align === "left" ? rect.width : 0);
    const x = Math.max(minimumX, Math.min(maximumX, left + point.x)) - left;
    const y =
      Math.max(
        bounds.top,
        Math.min(bounds.top + bounds.height - rect.height, top + point.y),
      ) - top;
    setOffset((current) =>
      current.x === x && current.y === y ? current : { x, y },
    );
  };
  useLayoutEffect(() => {
    move(currentOffset.current);
    const node = element.current;
    if (!node) return;
    const observer = new ResizeObserver(() => move(currentOffset.current));
    observer.observe(node);
    return () => observer.disconnect();
  }, [
    bounds.left,
    bounds.top,
    bounds.width,
    bounds.height,
    width,
    height,
    entries.length,
  ]);
  if (!entries.length) return null;
  return (
    <div
      ref={element}
      className={`plot-legend ${className}`}
      role="group"
      tabIndex={0}
      aria-label={label}
      aria-description="Drag to move within the plot. Arrow keys move it; Shift moves faster. Home or Escape restores its position."
      title="Drag to move · arrow keys move · Home restores"
      data-legend-offset={`${offset.x},${offset.y}`}
      style={{
        left: left + offset.x,
        top: top + offset.y,
        maxWidth: width,
        maxHeight: height,
        textAlign: align,
        transform: align === "right" ? "translateX(-100%)" : undefined,
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
          setOffset({ x: 0, y: 0 });
        } else if (deltas[event.key]) {
          event.preventDefault();
          event.stopPropagation();
          const [x, y] = deltas[event.key];
          move({ x: offset.x + x, y: offset.y + y });
        }
      }}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.focus({ preventScroll: true });
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = { x: event.clientX, y: event.clientY, start: offset };
      }}
      onPointerMove={(event) => {
        if (drag.current)
          move({
            x: drag.current.start.x + event.clientX - drag.current.x,
            y: drag.current.start.y + event.clientY - drag.current.y,
          });
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

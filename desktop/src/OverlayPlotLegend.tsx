import { useRef, useState } from "react";
import "./overlayPlotLegend.css";

/** Qt PatternWidget's borderless, right-aligned colored pattern names. */
export function OverlayPlotLegend({
  entries,
  left,
  top,
  width,
  height,
}: {
  entries: { name: string; color: string }[];
  left: number;
  top: number;
  width: number;
  height: number;
}) {
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; start: typeof offset } | null>(
    null,
  );
  return (
    <div
      className="overlay-plot-legend"
      aria-label="Pattern legend"
      style={{
        left: left + offset.x,
        top: top + offset.y,
        maxWidth: width,
        maxHeight: height,
      }}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = { x: event.clientX, y: event.clientY, start: offset };
      }}
      onPointerMove={(event) => {
        if (drag.current)
          setOffset({
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

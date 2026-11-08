import type { PointerEvent } from "react";

/** Shared pointer/keyboard resizing without adding chrome around scientific plots. */
export function LayoutDivider({
  className,
  label,
  orientation,
  value,
  min,
  max,
  defaultValue,
  step = 2,
  reverse = false,
  unit = "%",
  onChange,
  pointerValue,
  onDragStart,
}: {
  className: string;
  label: string;
  orientation: "vertical" | "horizontal";
  value: number;
  min: number;
  max: number;
  defaultValue: number;
  step?: number;
  reverse?: boolean;
  unit?: "%" | "px";
  onChange: (value: number) => void;
  pointerValue: (event: PointerEvent<HTMLDivElement>) => number | null;
  onDragStart?: (event: PointerEvent<HTMLDivElement>) => void;
}) {
  const update = (next: number) => onChange(Math.max(min, Math.min(max, next)));
  const release = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
  };
  return (
    <div
      className={className}
      role="separator"
      tabIndex={0}
      aria-label={label}
      aria-orientation={orientation}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={Math.max(
        min,
        Math.min(max, Math.round(value * 100) / 100),
      )}
      aria-valuetext={`${Math.round(value)}${unit}`}
      aria-description="Arrow keys resize; Shift moves faster. Home or double-click restores the default size. End expands to the maximum."
      title="Drag or use arrow keys to resize · Shift moves faster · Home or double-click resets"
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        onDragStart?.(event);
        event.currentTarget.setPointerCapture(event.pointerId);
        event.preventDefault();
      }}
      onPointerMove={(event) => {
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
        const next = pointerValue(event);
        if (next !== null) update(next);
      }}
      onPointerUp={release}
      onPointerCancel={release}
      onKeyDown={(event) => {
        const lower = orientation === "vertical" ? "ArrowLeft" : "ArrowUp",
          higher = orientation === "vertical" ? "ArrowRight" : "ArrowDown";
        if (![lower, higher, "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        event.stopPropagation();
        if (event.key === "Home") update(defaultValue);
        else if (event.key === "End") update(max);
        else
          update(
            value +
              (event.key === lower ? -1 : 1) *
                (reverse ? -1 : 1) *
                step *
                (event.shiftKey ? 5 : 1),
          );
      }}
      onDoubleClick={() => update(defaultValue)}
    >
      <span />
    </div>
  );
}

import type { PointerEvent } from "react";

/** Qt-like record-column sizing, local to this browser. */
export function DatabaseColumnResize({
  label,
  width,
  onWidth,
}: {
  label: string;
  width: number;
  onWidth: (width: number) => void;
}) {
  const clamp = (value: number) => Math.max(55, Math.min(600, value));
  const start = (event: PointerEvent<HTMLSpanElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const handle = event.currentTarget,
      left = event.clientX;
    handle.setPointerCapture(event.pointerId);
    const move = (e: globalThis.PointerEvent) =>
      onWidth(clamp(width + e.clientX - left));
    const finish = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", finish);
      handle.removeEventListener("lostpointercapture", finish);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", finish, { once: true });
    handle.addEventListener("lostpointercapture", finish, { once: true });
  };
  return (
    <span
      className="phase-database-column-resize"
      role="separator"
      aria-orientation="vertical"
      tabIndex={0}
      aria-label={`Resize ${label} column`}
      aria-valuenow={Math.round(width)}
      aria-valuemin={55}
      aria-valuemax={600}
      title="Drag to resize; double-click to fit contents. Left/right arrows adjust the width."
      onPointerDown={start}
      onKeyDown={(e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        e.preventDefault();
        e.stopPropagation();
        onWidth(clamp(width + (e.key === "ArrowRight" ? 10 : -10)));
      }}
      onDoubleClick={(e) => {
        const header = e.currentTarget.closest("th"),
          table = header?.closest("table");
        const context = document.createElement("canvas").getContext("2d");
        if (!header || !table || !context) return;
        let measured = 55;
        for (const row of table.rows) {
          const cell = row.cells[header.cellIndex];
          if (!cell) continue;
          context.font = getComputedStyle(cell).font;
          measured = Math.max(
            measured,
            context.measureText(cell.textContent || "").width + 30,
          );
        }
        onWidth(clamp(measured));
      }}
    />
  );
}

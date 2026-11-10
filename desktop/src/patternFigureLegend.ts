/** Paper legend layout is independent for measured curves and phase references. */
export type FigureLegendPosition =
  | "auto"
  | "top-left"
  | "top-right"
  | "bottom-left"
  | "bottom-right"
  | "above"
  | "below"
  | "right"
  | "none";
export type FigureLegendItem = {
  label: string;
  color: string;
  dash?: boolean;
  points?: boolean;
  line?: boolean;
  width: number;
  phase?: boolean;
};
export function wrapFigureText(
  ctx: CanvasRenderingContext2D,
  text: string,
  width: number,
) {
  const lines: string[] = [];
  let line = "";
  for (const ch of Array.from(text)) {
    if (line && ctx.measureText(line + ch).width > width) {
      lines.push(line);
      line = "";
    }
    line += ch;
  }
  lines.push(line);
  return lines;
}
export function layoutFigureLegend(
  ctx: CanvasRenderingContext2D,
  items: FigureLegendItem[],
  position: FigureLegendPosition,
  availableWidth: number,
  fontSize: number,
  title = "",
) {
  const active = position !== "none" && items.length > 0;
  const horizontal = position === "above" || position === "below";
  const columns = horizontal && availableWidth > fontSize * 28 ? 2 : 1;
  const width = horizontal
    ? availableWidth
    : Math.min(
        availableWidth * 0.39,
        Math.max(
          fontSize * 8,
          ...items.map(
            (item) => ctx.measureText(item.label).width + fontSize * 3,
          ),
          ctx.measureText(title).width + fontSize,
        ),
      );
  const lines = items.map((item) =>
    wrapFigureText(ctx, item.label, width / columns - fontSize * 3),
  );
  const rowHeights: number[] = [];
  for (let i = 0; i < items.length; i += columns)
    rowHeights.push(
      Math.max(...lines.slice(i, i + columns).map((row) => row.length)) *
        fontSize *
        1.4,
    );
  const titleHeight = title ? fontSize * 1.5 : 0;
  const height = active
    ? rowHeights.reduce((a, b) => a + b, 0) + fontSize * 0.7 + titleHeight
    : 0;
  return {
    items,
    position,
    active,
    horizontal,
    columns,
    width,
    height,
    lines,
    rowHeights,
    title,
    titleHeight,
  };
}
export type FigureLegendLayout = ReturnType<typeof layoutFigureLegend>;
export type FigureLegendBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};
export const figureBoxesOverlap = (
  a: FigureLegendBox,
  b: FigureLegendBox,
  gap = 0,
) =>
  a.x < b.x + b.width + gap &&
  a.x + a.width + gap > b.x &&
  a.y < b.y + b.height + gap &&
  a.y + a.height + gap > b.y;
export function drawFigureLegend(
  ctx: CanvasRenderingContext2D,
  legend: FigureLegendLayout,
  x: number,
  y: number,
  fs: number,
  ink: string,
  paper: string | null,
) {
  ctx.save();
  if (paper) {
    ctx.fillStyle = paper;
    ctx.fillRect(x, y, legend.width, legend.height);
  }
  ctx.textAlign = "left";
  ctx.fillStyle = ink;
  if (legend.title) ctx.fillText(legend.title, x + fs * 0.4, y + fs * 0.7);
  for (const [i, item] of legend.items.entries()) {
    const column = legend.horizontal ? i % legend.columns : 0;
    const row = legend.horizontal ? Math.floor(i / legend.columns) : i;
    const itemX = x + (column * legend.width) / legend.columns;
    const cy =
      y +
      legend.titleHeight +
      legend.rowHeights.slice(0, row).reduce((a, b) => a + b, 0) +
      fs * 0.7;
    ctx.strokeStyle = item.color;
    ctx.fillStyle = item.color;
    ctx.lineWidth = item.width;
    ctx.setLineDash(item.dash ? [4 * item.width, 2 * item.width] : []);
    if (item.phase) {
      for (const dx of [0.65, 1.2, 1.75]) {
        ctx.beginPath();
        ctx.moveTo(itemX + fs * dx, cy - fs * 0.35);
        ctx.lineTo(itemX + fs * dx, cy + fs * 0.35);
        ctx.stroke();
      }
    } else if (item.line) {
      ctx.beginPath();
      ctx.moveTo(itemX + fs * 0.4, cy);
      ctx.lineTo(itemX + fs * 2, cy);
      ctx.stroke();
    }
    if (item.points)
      ctx.fillRect(
        itemX + fs * 1.2 - item.width,
        cy - item.width,
        item.width * 2,
        item.width * 2,
      );
    ctx.setLineDash([]);
    ctx.fillStyle = ink;
    legend.lines[i].forEach((label, j) =>
      ctx.fillText(label, itemX + fs * 2.7, cy + j * fs * 1.4),
    );
  }
  ctx.restore();
}

export type FigureSegment = { x0: number; y0: number; x1: number; y1: number };
/** Clip a displayed segment against a candidate legend box, including sparse curves. */
export function figureSegmentIntersectsBox(
  segment: FigureSegment,
  box: FigureLegendBox,
) {
  let enter = 0,
    leave = 1;
  for (const [origin, delta, low, high] of [
    [segment.x0, segment.x1 - segment.x0, box.x, box.x + box.width],
    [segment.y0, segment.y1 - segment.y0, box.y, box.y + box.height],
  ]) {
    if (delta === 0) {
      if (origin < low || origin > high) return false;
    } else {
      const a = (low - origin) / delta,
        b = (high - origin) / delta;
      enter = Math.max(enter, Math.min(a, b));
      leave = Math.min(leave, Math.max(a, b));
    }
  }
  return enter <= leave;
}

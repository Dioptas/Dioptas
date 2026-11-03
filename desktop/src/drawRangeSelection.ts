export const RANGE_SELECTION_COLOR = "#66bfff";
export const BACKGROUND_RANGE_COLOR = "#ff9500";

/** Histogram-style range: translucent window, outlined edges and top handles. */
export function drawRangeSelection(
  context: CanvasRenderingContext2D,
  left: number,
  right: number,
  top: number,
  height: number,
  color: string,
  activeEdge?: "min" | "max",
  moving = false,
) {
  context.save();
  context.fillStyle = color + "1a";
  context.fillRect(left, top, right - left, height);
  if (moving) {
    context.fillStyle = color + "0d";
    context.fillRect(left, top, right - left, height);
  }
  for (const [edge, x] of [
    ["min", left],
    ["max", right],
  ] as const) {
    context.beginPath();
    context.moveTo(x, top);
    context.lineTo(x, top + height);
    context.strokeStyle = "#10151b";
    context.lineWidth = 5;
    context.stroke();
    context.strokeStyle =
      edge === activeEdge
        ? color === RANGE_SELECTION_COLOR
          ? "#a8dbff"
          : "#ffb347"
        : color;
    context.lineWidth = 2;
    context.stroke();
    context.fillStyle = color;
    context.beginPath();
    context.moveTo(x - 5, top);
    context.lineTo(x, top + 6);
    context.lineTo(x + 5, top);
    context.closePath();
    context.fill();
  }
  context.restore();
}

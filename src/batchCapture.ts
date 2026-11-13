/** Active Batch renderers register a synchronous PNG capture. The 3D renderer
 * can supply the same interface without coupling export to its implementation.
 * Return base64 PNG bytes (without the data URL prefix), or null if unavailable.
 */
export type BatchCapture = () => string | null;
export type BatchCaptureRef = { current: BatchCapture | null };

export function captureBatchCanvas(canvas: HTMLCanvasElement): string | null {
  if (!canvas.width || !canvas.height) return null;
  const output = document.createElement("canvas");
  output.width = canvas.width;
  output.height = canvas.height;
  const ctx = output.getContext("2d");
  if (!ctx) return null;
  // The display canvas is transparent over the application's charcoal surface.
  let background = "#191c20";
  for (
    let element: HTMLElement | null = canvas;
    element;
    element = element.parentElement
  ) {
    const color = getComputedStyle(element).backgroundColor;
    if (color && color !== "transparent" && color !== "rgba(0, 0, 0, 0)") {
      background = color;
      break;
    }
  }
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, output.width, output.height);
  ctx.drawImage(canvas, 0, 0);
  return output.toDataURL("image/png").split(",")[1];
}

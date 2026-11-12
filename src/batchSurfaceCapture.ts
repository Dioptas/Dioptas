/** Active-view hook for Batch's shared export workflow. Captures the rendered
 * surface, axes and selection at its bounded device-pixel size. No file dialog,
 * scientific export or data mutation belongs to this renderer.
 * Returns base64 PNG bytes (without a data URL prefix), matching BatchCapture.
 * Returns null when 3D is inactive/collapsed or its Canvas context is unavailable.
 */
export type BatchSurfaceCaptureRef = { current: (() => string | null) | null };

export function captureBatchSurface(
  root: ParentNode = document,
): string | null {
  const canvas = root.querySelector<HTMLCanvasElement>(
    '[data-testid="batch-surface"]',
  );
  if (
    !canvas ||
    canvas.closest("[hidden]") ||
    !canvas.clientWidth ||
    !canvas.clientHeight ||
    canvas.dataset.renderState !== "ready"
  )
    return null;
  try {
    return canvas.toDataURL("image/png").split(",")[1];
  } catch {
    return null;
  }
}

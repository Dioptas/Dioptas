import type { Raster } from "./types";
import { ByteCache } from "./rasterTransfer";
import { colorsFor } from "./colorMaps";

// Used only by PNG export and the Canvas fallback, never the normal GPU path.
const rendered = new ByteCache<string, HTMLCanvasElement>(96 * 1024 * 1024, 12);
export function rasterCanvas(
  raster: Raster,
  data: Float32Array | Uint8Array,
  mask: Raster | undefined,
  maskData: Float32Array | Uint8Array | null,
  lower: number,
  upper: number,
  log: boolean,
  palette: string,
  maskOpacity: number,
  precolored?: HTMLCanvasElement,
) {
  const colourImage =
    precolored ??
    (() => {
      const cacheKey = raster.bufferId
        ? JSON.stringify([
            "colour",
            raster.bufferId,
            raster.dtype,
            raster.width,
            raster.height,
            lower,
            upper,
            log,
            palette,
          ])
        : null;
      const cached = cacheKey ? rendered.get(cacheKey) : undefined;
      if (cached) return cached;
      const offscreen = document.createElement("canvas");
      offscreen.width = raster.width;
      offscreen.height = raster.height;
      const context = offscreen.getContext("2d")!;
      const pixels = context.createImageData(raster.width, raster.height);
      const span = Math.max(upper - lower, 1e-12);
      const ramp = colorsFor(palette),
        last = ramp.length - 1;
      const logSpan = Math.log1p(span);
      for (let i = 0; i < data.length; i++) {
        const value = data[i];
        const t = log
          ? Math.log1p(Math.max(0, value - lower)) / logSpan
          : (value - lower) / span;
        const k = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0)) * last;
        const index = Math.min(Math.floor(k), last - 1),
          fraction = k - index;
        const a = ramp[index],
          b = ramp[index + 1];
        const valid = Number.isFinite(value);
        for (let c = 0; c < 3; c++) {
          const intensity = valid
            ? Math.round(a[c] * (1 - fraction) + b[c] * fraction)
            : c === 0
              ? 23
              : c === 1
                ? 25
                : 30;
          pixels.data[4 * i + c] = intensity;
        }
        pixels.data[4 * i + 3] = 255;
      }
      context.putImageData(pixels, 0, 0);
      if (cacheKey)
        rendered.set(cacheKey, offscreen, 4 * raster.width * raster.height);
      return offscreen;
    })();
  return (() => {
    if (!maskData) return colourImage;
    const cacheKey =
      raster.bufferId && mask?.bufferId
        ? JSON.stringify([
            "mask",
            raster.bufferId,
            raster.dtype,
            raster.width,
            raster.height,
            mask.bufferId,
            lower,
            upper,
            log,
            palette,
            maskOpacity,
          ])
        : null;
    const cached = cacheKey ? rendered.get(cacheKey) : undefined;
    if (cached) return cached;
    // Reuse the unchanged detector colours. Drawing or changing opacity only
    // blends the mask pixels, without repeating log scaling or colour mapping.
    const pixels = colourImage
      .getContext("2d")!
      .getImageData(0, 0, raster.width, raster.height);
    const maskColor = [255, 0, 0];
    for (let i = 0; i < maskData.length; i++) {
      if (!maskData[i]) continue;
      for (let c = 0; c < 3; c++)
        pixels.data[4 * i + c] =
          maskColor[c] * maskOpacity +
          pixels.data[4 * i + c] * (1 - maskOpacity);
    }
    const offscreen = document.createElement("canvas");
    offscreen.width = raster.width;
    offscreen.height = raster.height;
    offscreen.getContext("2d")!.putImageData(pixels, 0, 0);
    if (cacheKey)
      rendered.set(cacheKey, offscreen, 4 * raster.width * raster.height);
    return offscreen;
  })();
}

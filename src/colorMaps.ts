import pyqtgraphMaps from "./pyqtgraph-colormaps.json";

export interface ColorMap {
  label: string;
  colors: number[][];
}
export const colorMaps: Record<string, ColorMap> = pyqtgraphMaps;
export function colorsFor(name: string) {
  return (colorMaps[name] ?? colorMaps.grey).colors;
}
export function rasterColor(t: number, palette: string) {
  const ramp = colorsFor(palette);
  const k = Math.max(0, Math.min(1, t)) * (ramp.length - 1);
  const i = Math.min(Math.floor(k), ramp.length - 2),
    f = k - i;
  return ramp[i].map((value, channel) =>
    Math.round(value * (1 - f) + ramp[i + 1][channel] * f),
  );
}

const previewCache = new Map<string, string>();
/** PNG ramp used by the picker, generated from the same lookup table as the image. */
export function colorMapPreview(name: string) {
  const saved = previewCache.get(name);
  if (saved) return saved;
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 1;
  const context = canvas.getContext("2d")!;
  const image = context.createImageData(256, 1);
  for (let i = 0; i < 256; i++) {
    const rgb = rasterColor(i / 255, name);
    image.data.set([...rgb, 255], i * 4);
  }
  context.putImageData(image, 0, 0);
  const url = canvas.toDataURL("image/png");
  previewCache.set(name, url);
  return url;
}

/** Keep overlay lines readable against the charcoal plot surface. */
export const OVERLAY_SCALE_BACKGROUND = [32, 34, 37];
export const OVERLAY_SCALE_MIN_CONTRAST = 3;

function luminance(rgb: number[]) {
  const linear = rgb.map((value) => {
    const channel = value / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

export function overlayColorContrast(rgb: number[]) {
  const foreground = luminance(rgb),
    background = luminance(OVERLAY_SCALE_BACKGROUND);
  return (
    (Math.max(foreground, background) + 0.05) /
    (Math.min(foreground, background) + 0.05)
  );
}

/** Trim dark endpoints, retaining the palette's actual colors and order. */
export function overlayScaleColors(
  ramp: number[][],
  count: number,
  reverse = false,
) {
  const first = ramp.findIndex(
    (rgb) => overlayColorContrast(rgb) >= OVERLAY_SCALE_MIN_CONTRAST,
  );
  const last =
    ramp.length -
    1 -
    [...ramp]
      .reverse()
      .findIndex(
        (rgb) => overlayColorContrast(rgb) >= OVERLAY_SCALE_MIN_CONTRAST,
      );
  if (first < 0 || count <= 0) return [];
  return Array.from({ length: count }, (_, index) => {
    let t = count === 1 ? 0.5 : index / (count - 1);
    if (reverse) t = 1 - t;
    const k = first + t * (last - first),
      i = Math.floor(k),
      f = k - i;
    const rgb = ramp[i].map((value, channel) =>
      Math.round(value * (1 - f) + ramp[Math.min(i + 1, last)][channel] * f),
    );
    return (
      "#" + rgb.map((value) => value.toString(16).padStart(2, "0")).join("")
    );
  });
}

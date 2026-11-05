type Rect = { left: number; top: number; width: number; height: number };
type Point = { x: number; y: number };
/** Pick an in-plot corner with fewer curve samples and no labelled controls. */
export function legendPlacement(
  bounds: Rect,
  width: number,
  height: number,
  points: Point[],
  obstacles: Rect[],
) {
  const w = Math.min(width, bounds.width),
    h = Math.min(height, bounds.height);
  const x0 = bounds.left + Math.min(8, Math.max(0, (bounds.width - w) / 2)),
    x1 =
      bounds.left +
      bounds.width -
      w -
      Math.min(8, Math.max(0, (bounds.width - w) / 2));
  const y0 = bounds.top + Math.min(5, Math.max(0, (bounds.height - h) / 2)),
    y1 =
      bounds.top +
      bounds.height -
      h -
      Math.min(5, Math.max(0, (bounds.height - h) / 2));
  const candidates = [
    { x: x1, y: y0, align: "right" as const },
    { x: x1, y: y1, align: "right" as const },
    { x: x0, y: y0, align: "left" as const },
    { x: x0, y: y1, align: "left" as const },
  ];
  const score = (r: (typeof candidates)[number]) =>
    points.filter(
      (p) =>
        p.x >= r.x - 4 &&
        p.x <= r.x + w + 4 &&
        p.y >= r.y - 4 &&
        p.y <= r.y + h + 4,
    ).length +
    obstacles.reduce(
      (total, o) =>
        total +
        (Math.min(r.x + w, o.left + o.width) > Math.max(r.x, o.left) &&
        Math.min(r.y + h, o.top + o.height) > Math.max(r.y, o.top)
          ? 10000
          : 0),
      0,
    );
  const best = candidates.reduce((best, next) =>
    score(next) < score(best) ? next : best,
  );
  return {
    left: best.align === "right" ? best.x + w : best.x,
    top: best.y,
    align: best.align,
  };
}

/** Keep each bucket's extrema so a narrow diffraction peak cannot be skipped. */
export function* legendSampleIndices(
  x: readonly number[],
  y: readonly (number | null)[],
  start: number,
  end: number,
  buckets = 128,
): Generator<number> {
  const step = Math.max(1, Math.ceil((end - start) / buckets));
  for (let first = start; first < end; first += step) {
    let low = -1,
      high = -1;
    for (let i = first; i < Math.min(end, first + step); i++) {
      const value = y[i];
      if (!Number.isFinite(x[i]) || value == null || !Number.isFinite(value))
        continue;
      if (low < 0 || value < y[low]!) low = i;
      if (high < 0 || value > y[high]!) high = i;
    }
    if (low >= 0) yield low;
    if (high >= 0 && high !== low) yield high;
  }
}

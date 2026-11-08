/** Index immutable x arrays once. q/2theta ascend; d usually descends.
 * Unsorted/nonfinite coordinates retain the general linear path. */
const orders = new WeakMap<number[], number>();
function order(x: number[]) {
  const cached = orders.get(x);
  if (cached !== undefined) return cached;
  let direction = 0;
  for (let i = 0; i < x.length; i++) {
    if (!Number.isFinite(x[i])) {
      direction = 0;
      break;
    }
    if (!i || x[i] === x[i - 1]) continue;
    const next = Math.sign(x[i] - x[i - 1]);
    if (direction && next !== direction) {
      direction = 0;
      break;
    }
    direction = next;
  }
  if (!direction && x.every((v) => Number.isFinite(v) && v === x[0]))
    direction = 1;
  orders.set(x, direction);
  return direction;
}
function bound(x: number[], value: number, direction: number, upper: boolean) {
  let low = 0,
    high = x.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    const delta = (x[middle] - value) * direction;
    if (delta < 0 || (upper && delta === 0)) low = middle + 1;
    else high = middle;
  }
  return low;
}
/** Half-open interval, including neighbours for segments crossing view edges. */
export function visibleSamples(
  x: number[],
  min: number,
  max: number,
  neighbours = true,
): [number, number] {
  const direction = order(x);
  if (!direction) return [0, x.length];
  const start = bound(x, direction > 0 ? min : max, direction, false);
  const end = bound(x, direction > 0 ? max : min, direction, true);
  const pad = Number(neighbours);
  return [Math.max(0, start - pad), Math.min(x.length, end + pad)];
}
export function nearestSample(x: number[], value: number) {
  if (!x.length) return -1;
  const direction = order(x);
  if (!direction) {
    let best = -1,
      distance = Infinity;
    for (let i = 0; i < x.length; i++) {
      if (!Number.isFinite(x[i])) continue;
      const delta = Math.abs(x[i] - value);
      if (delta < distance) {
        best = i;
        distance = delta;
      }
    }
    return best;
  }
  const right = bound(x, value, direction, false);
  if (!right) return 0;
  if (right === x.length) return bound(x, x[x.length - 1], direction, false);
  const best =
    Math.abs(x[right] - value) < Math.abs(x[right - 1] - value)
      ? right
      : right - 1;
  return bound(x, x[best], direction, false);
}

const orderedIndices = new WeakMap<number[], number[]>();
export type InspectionDirection = "previous" | "next" | "first" | "last";

/** Read-only sample traversal follows increasing visual x, including descending
 * d-spacing and imperfect/unsorted input files. Source arrays are never sorted. */
export function* sampleInspectionOrder(
  x: number[],
  min: number,
  max: number,
  current: number | null,
  action: InspectionDirection,
): Generator<number> {
  const direction = order(x);
  if (direction) {
    const [start, end] = visibleSamples(x, min, max, false);
    if (start >= end) return;
    const step =
      (action === "previous" || action === "last" ? -1 : 1) * direction;
    const base =
      current !== null && current >= start && current < end
        ? current
        : nearestSample(x, (min + max) / 2);
    const index =
      action === "first"
        ? direction > 0
          ? start
          : end - 1
        : action === "last"
          ? direction > 0
            ? end - 1
            : start
          : Math.max(start, Math.min(end - 1, base + step));
    for (let i = index; i >= start && i < end; i += step) yield i;
    return;
  }
  let sorted = orderedIndices.get(x);
  if (!sorted) {
    sorted = x
      .map((_, i) => i)
      .filter((i) => Number.isFinite(x[i]))
      .sort((a, b) => x[a] - x[b] || a - b);
    orderedIndices.set(x, sorted);
  }
  const visible = sorted.filter((i) => x[i] >= min && x[i] <= max);
  if (!visible.length) return;
  const step = action === "previous" || action === "last" ? -1 : 1;
  let base = current === null ? -1 : visible.indexOf(current);
  if (base < 0)
    base = visible.reduce(
      (best, index, position) =>
        Math.abs(x[index] - (min + max) / 2) <
        Math.abs(x[visible[best]] - (min + max) / 2)
          ? position
          : best,
      0,
    );
  const position =
    action === "first"
      ? 0
      : action === "last"
        ? visible.length - 1
        : Math.max(0, Math.min(visible.length - 1, base + step));
  for (let i = position; i >= 0 && i < visible.length; i += step)
    yield visible[i];
}

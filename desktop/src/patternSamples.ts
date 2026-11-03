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
  if (!direction)
    return x.reduce(
      (best, v, i) =>
        Math.abs(v - value) < Math.abs(x[best] - value) ? i : best,
      0,
    );
  const right = bound(x, value, direction, false);
  if (!right) return 0;
  if (right === x.length) return bound(x, x[x.length - 1], direction, false);
  const best =
    Math.abs(x[right] - value) < Math.abs(x[right - 1] - value)
      ? right
      : right - 1;
  return bound(x, x[best], direction, false);
}

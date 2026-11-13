/** Project radial positions into stored column bins, including descending d. */
export function batchRadialBin(
  x: number,
  coordinates: number[],
): number | null {
  const last = coordinates.length - 1;
  if (last < 0 || !Number.isFinite(x)) return null;
  if (
    x < Math.min(coordinates[0], coordinates[last]) ||
    x > Math.max(coordinates[0], coordinates[last])
  )
    return null;
  if (last === 0) return 0.5;
  const ascending = coordinates[last] > coordinates[0];
  let low = 0,
    high = last;
  while (high - low > 1) {
    const mid = (low + high) >>> 1;
    if (coordinates[mid] < x === ascending) low = mid;
    else high = mid;
  }
  const fraction =
    (x - coordinates[low]) / (coordinates[high] - coordinates[low]);
  return low + Math.max(0, Math.min(1, fraction)) + 0.5;
}

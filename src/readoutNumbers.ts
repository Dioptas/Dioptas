const number = (n: number, digits: number) =>
  n.toLocaleString("en-US", { maximumFractionDigits: digits });

export function intensityValue(n: number | null | undefined) {
  if (n == null || !Number.isFinite(n)) return "—";
  // Integer detector counts are exact; interpolated/processed values need fewer digits.
  if (Number.isInteger(n) && Math.abs(n) < 1e7) return number(n, 0);
  const rounded = Number(n.toPrecision(4));
  const text = number(rounded, 6);
  return text.length > 9 || (n !== 0 && Math.abs(n) < 0.001)
    ? rounded.toExponential(3)
    : text;
}

/** Coordinate precision follows approximately one screen pixel, including zoom. */
export function coordinateValue(n: number, resolution = 0.01) {
  if (!Number.isFinite(n)) return "—";
  const step =
    Number.isFinite(resolution) && resolution > 0 ? resolution : 0.01;
  const requestedDigits = Math.max(0, Math.ceil(-Math.log10(step)));
  const digits = Math.min(6, requestedDigits);
  const text = number(n, digits);
  if (n === 0 || (text.length <= 9 && requestedDigits <= 6)) return text;
  // Keep visible differences when zoomed closely around a large axis offset.
  const significant = Math.max(
    0,
    Math.min(12, Math.floor(Math.log10(Math.abs(n) / step))),
  );
  return n.toExponential(significant);
}

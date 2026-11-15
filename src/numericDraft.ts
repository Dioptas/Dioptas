export type NumericLimits = {
  min?: number;
  max?: number;
  positive?: boolean;
  integer?: boolean;
  unit?: string;
};

/** Empty/partial native input text is never a valid zero. */
export function numericDraftError(text: string, limits: NumericLimits = {}) {
  if (!text.trim() || !Number.isFinite(Number(text)))
    return "Enter a finite number.";
  const value = Number(text);
  const limitLabel = (number: number) =>
    `${Number.isInteger(number) ? number : `≈ ${Number(number.toPrecision(7))}`}${limits.unit ? ` ${limits.unit}` : ""}`.replaceAll(
      "-",
      "−",
    );
  if (limits.integer && !Number.isInteger(value))
    return "Enter a whole number.";
  if (limits.positive && value <= 0) return "Enter a value greater than zero.";
  if (limits.min !== undefined && value < limits.min)
    return `Enter a value of at least ${limitLabel(limits.min)}.`;
  if (limits.max !== undefined && value > limits.max)
    return `Enter a value no greater than ${limitLabel(limits.max)}.`;
  return null;
}

/** One spin step: the next multiple of `step` above/below `value`, kept in
 * the limits and rounded to the step's decimals (0.5 + 0.1 shows 0.6, not
 * 0.6000000000000001). */
export function stepNumber(
  value: number,
  step: number,
  direction: 1 | -1,
  limits: NumericLimits = {},
) {
  const decimals = (String(step).split(".")[1] ?? "").length;
  const units = value / step;
  // From a value between grid points, the first step lands on the grid.
  const near = Math.round(units);
  const onGrid = Math.abs(units - near) < 1e-9;
  let next =
    (onGrid
      ? near + direction
      : direction > 0
        ? Math.ceil(units)
        : Math.floor(units)) * step;
  next = Number(next.toFixed(decimals));
  const lowest = limits.min ?? (limits.positive ? step : -Infinity);
  if (next < lowest) next = limits.min ?? value;
  if (limits.max !== undefined && next > limits.max) next = limits.max;
  if (limits.integer) next = Math.round(next);
  return next;
}

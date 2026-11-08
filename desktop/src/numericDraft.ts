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
